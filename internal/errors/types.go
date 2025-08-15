package errors

import (
	"fmt"

	errorspb "github.com/bhatti/todo-api-errors/api/proto/errors/v1"
	"google.golang.org/genproto/googleapis/rpc/errdetails"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/anypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// AppError is our custom error type using protobuf definitions.
type AppError struct {
	GRPCCode        codes.Code
	AppCode         errorspb.AppErrorCode
	Title           string
	Detail          string
	FieldViolations []*errorspb.FieldViolation
	TraceID         string
	Instance        string
	Extensions      map[string]*anypb.Any
	CausedBy        error // For internal logging
}

func (e *AppError) Error() string {
	return fmt.Sprintf("gRPC Code: %s, App Code: %s, Title: %s, Detail: %s", e.GRPCCode, e.AppCode, e.Title, e.Detail)
}

// ToGRPCStatus converts our AppError into a gRPC status.Status.
func (e *AppError) ToGRPCStatus() *status.Status {
	st := status.New(e.GRPCCode, e.Title)

	errorDetail := &errorspb.ErrorDetail{
		Code:            e.AppCode.String(),
		Title:           e.Title,
		Detail:          e.Detail,
		FieldViolations: e.FieldViolations,
		TraceId:         e.TraceID,
		Timestamp:       timestamppb.Now(),
		Instance:        e.Instance,
		Extensions:      e.Extensions,
	}

	// For validation errors, we also attach the standard BadRequest detail
	// so that gRPC-Gateway and other standard tools can understand it.
	if e.GRPCCode == codes.InvalidArgument && len(e.FieldViolations) > 0 {
		br := &errdetails.BadRequest{}
		for _, fv := range e.FieldViolations {
			br.FieldViolations = append(br.FieldViolations, &errdetails.BadRequest_FieldViolation{
				Field:       fv.Field,
				Description: fv.Description,
			})
		}
		st, _ = st.WithDetails(br, errorDetail)
		return st
	}

	st, _ = st.WithDetails(errorDetail)
	return st
}

// Helper functions for creating common errors

func NewValidationFailed(violations []*errorspb.FieldViolation, traceID string) *AppError {
	return &AppError{
		GRPCCode:        codes.InvalidArgument,
		AppCode:         errorspb.AppErrorCode_VALIDATION_FAILED,
		Title:           "Validation Failed",
		Detail:          fmt.Sprintf("The request contains %d validation errors", len(violations)),
		FieldViolations: violations,
		TraceID:         traceID,
	}
}

func NewNotFound(resource string, id string, traceID string) *AppError {
	return &AppError{
		GRPCCode: codes.NotFound,
		AppCode:  errorspb.AppErrorCode_RESOURCE_NOT_FOUND,
		Title:    "Resource Not Found",
		Detail:   fmt.Sprintf("%s with ID '%s' was not found.", resource, id),
		TraceID:  traceID,
	}
}

func NewConflict(resource, reason string, traceID string) *AppError {
	return &AppError{
		GRPCCode: codes.AlreadyExists,
		AppCode:  errorspb.AppErrorCode_RESOURCE_CONFLICT,
		Title:    "Resource Conflict",
		Detail:   fmt.Sprintf("Conflict creating %s: %s", resource, reason),
		TraceID:  traceID,
	}
}

func NewInternal(message string, traceID string, causedBy error) *AppError {
	return &AppError{
		GRPCCode: codes.Internal,
		AppCode:  errorspb.AppErrorCode_INTERNAL_ERROR,
		Title:    "Internal Server Error",
		Detail:   message,
		TraceID:  traceID,
		CausedBy: causedBy,
	}
}

func NewPermissionDenied(resource, action string, traceID string) *AppError {
	return &AppError{
		GRPCCode: codes.PermissionDenied,
		AppCode:  errorspb.AppErrorCode_PERMISSION_DENIED,
		Title:    "Permission Denied",
		Detail:   fmt.Sprintf("You don't have permission to %s %s", action, resource),
		TraceID:  traceID,
	}
}

func NewServiceUnavailable(message string, traceID string) *AppError {
	return &AppError{
		GRPCCode: codes.Unavailable,
		AppCode:  errorspb.AppErrorCode_SERVICE_UNAVAILABLE,
		Title:    "Service Unavailable",
		Detail:   message,
		TraceID:  traceID,
	}
}

func NewRequiredField(field, message string, traceID string) *AppError {
	return &AppError{
		GRPCCode: codes.InvalidArgument,
		AppCode:  errorspb.AppErrorCode_VALIDATION_FAILED,
		Title:    "Validation Failed",
		Detail:   "The request contains validation errors",
		FieldViolations: []*errorspb.FieldViolation{
			{
				Field:       field,
				Code:        errorspb.AppErrorCode_REQUIRED_FIELD.String(),
				Description: message,
			},
		},
		TraceID: traceID,
	}
}
