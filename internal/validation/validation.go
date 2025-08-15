package validation

import (
	"errors"
	"fmt"
	"regexp"
	"strings"

	"buf.build/gen/go/bufbuild/protovalidate/protocolbuffers/go/buf/validate"
	"buf.build/go/protovalidate"
	errorspb "github.com/bhatti/todo-api-errors/api/proto/errors/v1"
	todopb "github.com/bhatti/todo-api-errors/api/proto/todo/v1"
	apperrors "github.com/bhatti/todo-api-errors/internal/errors"
	"google.golang.org/protobuf/proto"
)

var pv protovalidate.Validator

func init() {
	var err error
	pv, err = protovalidate.New()
	if err != nil {
		panic(fmt.Sprintf("failed to initialize protovalidator: %v", err))
	}
}

// ValidateRequest checks a proto message and returns an AppError with all violations.
func ValidateRequest(req proto.Message, traceID string) error {
	if err := pv.Validate(req); err != nil {
		var validationErrs *protovalidate.ValidationError
		if errors.As(err, &validationErrs) {
			var violations []*errorspb.FieldViolation
			for _, violation := range validationErrs.Violations {
				fieldPath := ""
				if violation.Proto.GetField() != nil {
					fieldPath = formatFieldPath(violation.Proto.GetField())
				}

				ruleId := violation.Proto.GetRuleId()
				message := violation.Proto.GetMessage()

				violations = append(violations, &errorspb.FieldViolation{
					Field:       fieldPath,
					Description: message,
					Code:        mapConstraintToCode(ruleId),
				})
			}
			return apperrors.NewValidationFailed(violations, traceID)
		}
		return apperrors.NewInternal("Validation failed", traceID, err)
	}
	return nil
}

// ValidateTask performs additional business logic validation
func ValidateTask(task *todopb.Task, traceID string) error {
	var violations []*errorspb.FieldViolation

	// Proto validation first
	if err := ValidateRequest(task, traceID); err != nil {
		if appErr, ok := err.(*apperrors.AppError); ok {
			violations = append(violations, appErr.FieldViolations...)
		}
	}

	// Additional business rules
	if task.Status == todopb.Status_STATUS_COMPLETED && task.DueDate != nil {
		if task.UpdateTime != nil && task.UpdateTime.AsTime().After(task.DueDate.AsTime()) {
			violations = append(violations, &errorspb.FieldViolation{
				Field:       "due_date",
				Code:        errorspb.AppErrorCode_OVERDUE_COMPLETION.String(),
				Description: "Task was completed after the due date",
			})
		}
	}

	// Validate tags format
	for i, tag := range task.Tags {
		if !isValidTag(tag) {
			violations = append(violations, &errorspb.FieldViolation{
				Field:       fmt.Sprintf("tags[%d]", i),
				Code:        errorspb.AppErrorCode_INVALID_TAG_FORMAT.String(),
				Description: fmt.Sprintf("Tag '%s' must be lowercase letters, numbers, and hyphens only", tag),
			})
		}
	}

	// Check for duplicate tags
	tagMap := make(map[string]bool)
	for i, tag := range task.Tags {
		if tagMap[tag] {
			violations = append(violations, &errorspb.FieldViolation{
				Field:       fmt.Sprintf("tags[%d]", i),
				Code:        errorspb.AppErrorCode_DUPLICATE_TAG.String(),
				Description: fmt.Sprintf("Tag '%s' appears multiple times", tag),
			})
		}
		tagMap[tag] = true
	}

	if len(violations) > 0 {
		return apperrors.NewValidationFailed(violations, traceID)
	}

	return nil
}

// ValidateBatchCreateTasks validates batch operations
func ValidateBatchCreateTasks(req *todopb.BatchCreateTasksRequest, traceID string) error {
	var violations []*errorspb.FieldViolation

	// Check batch size
	if len(req.Requests) == 0 {
		violations = append(violations, &errorspb.FieldViolation{
			Field:       "requests",
			Code:        errorspb.AppErrorCode_EMPTY_BATCH.String(),
			Description: "Batch must contain at least one task",
		})
	}

	if len(req.Requests) > 100 {
		violations = append(violations, &errorspb.FieldViolation{
			Field:       "requests",
			Code:        errorspb.AppErrorCode_BATCH_TOO_LARGE.String(),
			Description: fmt.Sprintf("Batch size %d exceeds maximum of 100", len(req.Requests)),
		})
	}

	// Validate each task
	for i, createReq := range req.Requests {
		if createReq.Task == nil {
			violations = append(violations, &errorspb.FieldViolation{
				Field:       fmt.Sprintf("requests[%d].task", i),
				Code:        errorspb.AppErrorCode_REQUIRED_FIELD.String(),
				Description: "Task is required",
			})
			continue
		}

		// Validate task
		if err := ValidateTask(createReq.Task, traceID); err != nil {
			if appErr, ok := err.(*apperrors.AppError); ok {
				for _, violation := range appErr.FieldViolations {
					violation.Field = fmt.Sprintf("requests[%d].task.%s", i, violation.Field)
					violations = append(violations, violation)
				}
			}
		}
	}

	// Check for duplicate titles
	titleMap := make(map[string][]int)
	for i, createReq := range req.Requests {
		if createReq.Task != nil && createReq.Task.Title != "" {
			titleMap[createReq.Task.Title] = append(titleMap[createReq.Task.Title], i)
		}
	}

	for title, indices := range titleMap {
		if len(indices) > 1 {
			for _, idx := range indices {
				violations = append(violations, &errorspb.FieldViolation{
					Field:       fmt.Sprintf("requests[%d].task.title", idx),
					Code:        errorspb.AppErrorCode_DUPLICATE_TITLE.String(),
					Description: fmt.Sprintf("Title '%s' is used by multiple tasks in the batch", title),
				})
			}
		}
	}

	if len(violations) > 0 {
		return apperrors.NewValidationFailed(violations, traceID)
	}

	return nil
}

// Helper functions
func formatFieldPath(fieldPath *validate.FieldPath) string {
	if fieldPath == nil {
		return ""
	}

	// Build field path from elements
	var parts []string
	for _, element := range fieldPath.GetElements() {
		if element.GetFieldName() != "" {
			parts = append(parts, element.GetFieldName())
		} else if element.GetFieldNumber() != 0 {
			parts = append(parts, fmt.Sprintf("field_%d", element.GetFieldNumber()))
		}
	}

	return strings.Join(parts, ".")
}

func mapConstraintToCode(ruleId string) string {
	switch {
	case strings.Contains(ruleId, "required"):
		return errorspb.AppErrorCode_REQUIRED_FIELD.String()
	case strings.Contains(ruleId, "min_len"):
		return errorspb.AppErrorCode_TOO_SHORT.String()
	case strings.Contains(ruleId, "max_len"):
		return errorspb.AppErrorCode_TOO_LONG.String()
	case strings.Contains(ruleId, "pattern"):
		return errorspb.AppErrorCode_INVALID_FORMAT.String()
	case strings.Contains(ruleId, "gt_now"):
		return errorspb.AppErrorCode_MUST_BE_FUTURE.String()
	case ruleId == "":
		return errorspb.AppErrorCode_VALIDATION_FAILED.String()
	default:
		return errorspb.AppErrorCode_INVALID_VALUE.String()
	}
}

var validTagPattern = regexp.MustCompile(`^[a-z0-9-]+$`)

func isValidTag(tag string) bool {
	return len(tag) <= 50 && validTagPattern.MatchString(tag)
}
