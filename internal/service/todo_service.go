package service

import (
	"context"
	"fmt"
	todopb "github.com/bhatti/todo-api-errors/api/proto/todo/v1"
	"github.com/bhatti/todo-api-errors/internal/errors"
	"github.com/bhatti/todo-api-errors/internal/repository"
	"github.com/bhatti/todo-api-errors/internal/validation"
	"github.com/google/uuid"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
	"google.golang.org/protobuf/types/known/fieldmaskpb"
	"google.golang.org/protobuf/types/known/timestamppb"
	"strings"
)

var tracer = otel.Tracer("todo-service")

// TodoService implements the TODO API
type TodoService struct {
	todopb.UnimplementedTodoServiceServer
	repo repository.TodoRepository
}

// NewTodoService creates a new TODO service
func NewTodoService(repo repository.TodoRepository) (*TodoService, error) {
	return &TodoService{
		repo: repo,
	}, nil
}

// CreateTask creates a new task
func (s *TodoService) CreateTask(ctx context.Context, req *todopb.CreateTaskRequest) (*todopb.Task, error) {
	ctx, span := tracer.Start(ctx, "CreateTask")
	defer span.End()

	// Get trace ID for error responses
	traceID := span.SpanContext().TraceID().String()

	// Validate request
	if req.Task == nil {
		return nil, errors.NewRequiredField("task", "Task object is required", traceID)
	}

	// Validate task fields using the new validation package
	if err := validation.ValidateTask(req.Task, traceID); err != nil {
		span.SetAttributes(attribute.String("validation.error", err.Error()))
		return nil, err
	}

	// Check for duplicate title
	existing, err := s.repo.GetTaskByTitle(ctx, req.Task.Title)
	if err != nil && !repository.IsNotFound(err) {
		span.RecordError(err)
		return nil, s.handleRepositoryError(err, traceID)
	}

	if existing != nil {
		return nil, errors.NewConflict("task", "A task with this title already exists", traceID)
	}

	// Generate task ID
	taskID := uuid.New().String()
	task := &todopb.Task{
		Name:        fmt.Sprintf("tasks/%s", taskID),
		Title:       req.Task.Title,
		Description: req.Task.Description,
		Status:      req.Task.Status,
		Priority:    req.Task.Priority,
		DueDate:     req.Task.DueDate,
		Tags:        req.Task.Tags,
		CreateTime:  timestamppb.Now(),
		UpdateTime:  timestamppb.Now(),
		CreatedBy:   s.getUserFromContext(ctx),
	}

	// Set defaults
	if task.Status == todopb.Status_STATUS_UNSPECIFIED {
		task.Status = todopb.Status_STATUS_PENDING
	}
	if task.Priority == todopb.Priority_PRIORITY_UNSPECIFIED {
		task.Priority = todopb.Priority_PRIORITY_MEDIUM
	}

	// Save to repository
	if err := s.repo.CreateTask(ctx, task); err != nil {
		span.RecordError(err)
		return nil, s.handleRepositoryError(err, traceID)
	}

	span.SetAttributes(
		attribute.String("task.id", taskID),
		attribute.String("task.title", task.Title),
	)

	return task, nil
}

// GetTask retrieves a specific task
func (s *TodoService) GetTask(ctx context.Context, req *todopb.GetTaskRequest) (*todopb.Task, error) {
	ctx, span := tracer.Start(ctx, "GetTask")
	defer span.End()

	traceID := span.SpanContext().TraceID().String()

	// Validate request using the new validation package
	if err := validation.ValidateRequest(req, traceID); err != nil {
		return nil, err
	}

	// Extract task ID
	parts := strings.Split(req.Name, "/")
	if len(parts) != 2 || parts[0] != "tasks" {
		return nil, errors.NewRequiredField("name", "Task name must be in format 'tasks/{id}'", traceID)
	}

	taskID := parts[1]
	span.SetAttributes(attribute.String("task.id", taskID))

	// Get from repository
	task, err := s.repo.GetTask(ctx, taskID)
	if err != nil {
		if repository.IsNotFound(err) {
			return nil, errors.NewNotFound("Task", taskID, traceID)
		}
		span.RecordError(err)
		return nil, s.handleRepositoryError(err, traceID)
	}

	// Check permissions
	if !s.canAccessTask(ctx, task) {
		return nil, errors.NewPermissionDenied("task", "read", traceID)
	}

	return task, nil
}

// ListTasks retrieves all tasks
func (s *TodoService) ListTasks(ctx context.Context, req *todopb.ListTasksRequest) (*todopb.ListTasksResponse, error) {
	ctx, span := tracer.Start(ctx, "ListTasks")
	defer span.End()

	traceID := span.SpanContext().TraceID().String()

	// Validate request using the new validation package
	if err := validation.ValidateRequest(req, traceID); err != nil {
		return nil, err
	}

	// Default page size
	pageSize := req.PageSize
	if pageSize == 0 {
		pageSize = 50
	}
	if pageSize > 1000 {
		pageSize = 1000
	}

	span.SetAttributes(
		attribute.Int("page.size", int(pageSize)),
		attribute.String("filter", req.Filter),
	)

	// Parse filter
	filter, err := s.parseFilter(req.Filter)
	if err != nil {
		return nil, errors.NewRequiredField("filter", fmt.Sprintf("Failed to parse filter: %v", err), traceID)
	}

	// Get tasks from repository
	tasks, nextPageToken, err := s.repo.ListTasks(ctx, repository.ListOptions{
		PageSize:  int(pageSize),
		PageToken: req.PageToken,
		Filter:    filter,
		OrderBy:   req.OrderBy,
		UserID:    s.getUserFromContext(ctx),
	})

	if err != nil {
		span.RecordError(err)
		return nil, s.handleRepositoryError(err, traceID)
	}

	// Get total count
	totalSize, err := s.repo.CountTasks(ctx, filter, s.getUserFromContext(ctx))
	if err != nil {
		// Log but don't fail the request
		span.RecordError(err)
		totalSize = -1
	}

	return &todopb.ListTasksResponse{
		Tasks:         tasks,
		NextPageToken: nextPageToken,
		TotalSize:     int32(totalSize),
	}, nil
}

// UpdateTask updates an existing task
func (s *TodoService) UpdateTask(ctx context.Context, req *todopb.UpdateTaskRequest) (*todopb.Task, error) {
	ctx, span := tracer.Start(ctx, "UpdateTask")
	defer span.End()

	traceID := span.SpanContext().TraceID().String()

	// Validate request
	if req.Task == nil {
		return nil, errors.NewRequiredField("task", "Task object is required", traceID)
	}

	if req.UpdateMask == nil || len(req.UpdateMask.Paths) == 0 {
		return nil, errors.NewRequiredField("update_mask", "Update mask must specify which fields to update", traceID)
	}

	// Extract task ID
	parts := strings.Split(req.Task.Name, "/")
	if len(parts) != 2 || parts[0] != "tasks" {
		return nil, errors.NewRequiredField("task.name", "Invalid task name format", traceID)
	}

	taskID := parts[1]
	span.SetAttributes(attribute.String("task.id", taskID))

	// Get existing task
	existing, err := s.repo.GetTask(ctx, taskID)
	if err != nil {
		if repository.IsNotFound(err) {
			return nil, errors.NewNotFound("Task", taskID, traceID)
		}
		return nil, s.handleRepositoryError(err, traceID)
	}

	// Check permissions
	if !s.canModifyTask(ctx, existing) {
		return nil, errors.NewPermissionDenied("task", "update", traceID)
	}

	// Apply updates based on field mask
	updated := s.applyFieldMask(existing, req.Task, req.UpdateMask)
	updated.UpdateTime = timestamppb.Now()

	// Validate updated task using the new validation package
	if err := validation.ValidateTask(updated, traceID); err != nil {
		return nil, err
	}

	// Save to repository
	if err := s.repo.UpdateTask(ctx, updated); err != nil {
		span.RecordError(err)
		return nil, s.handleRepositoryError(err, traceID)
	}

	return updated, nil
}

// DeleteTask removes a task
func (s *TodoService) DeleteTask(ctx context.Context, req *todopb.DeleteTaskRequest) (*todopb.DeleteTaskResponse, error) {
	ctx, span := tracer.Start(ctx, "DeleteTask")
	defer span.End()

	traceID := span.SpanContext().TraceID().String()

	// Validate request using the new validation package
	if err := validation.ValidateRequest(req, traceID); err != nil {
		return nil, err
	}

	// Extract task ID
	parts := strings.Split(req.Name, "/")
	if len(parts) != 2 || parts[0] != "tasks" {
		return nil, errors.NewRequiredField("name", "Invalid task name format", traceID)
	}

	taskID := parts[1]
	span.SetAttributes(attribute.String("task.id", taskID))

	// Get existing task to check permissions
	existing, err := s.repo.GetTask(ctx, taskID)
	if err != nil {
		if repository.IsNotFound(err) {
			return nil, errors.NewNotFound("Task", taskID, traceID)
		}
		return nil, s.handleRepositoryError(err, traceID)
	}

	// Check permissions
	if !s.canModifyTask(ctx, existing) {
		return nil, errors.NewPermissionDenied("task", "delete", traceID)
	}

	// Delete from repository
	if err := s.repo.DeleteTask(ctx, taskID); err != nil {
		span.RecordError(err)
		return nil, s.handleRepositoryError(err, traceID)
	}

	return &todopb.DeleteTaskResponse{
		Message: fmt.Sprintf("Task %s deleted successfully", req.Name),
	}, nil
}

// BatchCreateTasks creates multiple tasks at once
func (s *TodoService) BatchCreateTasks(ctx context.Context, req *todopb.BatchCreateTasksRequest) (*todopb.BatchCreateTasksResponse, error) {
	ctx, span := tracer.Start(ctx, "BatchCreateTasks")
	defer span.End()

	traceID := span.SpanContext().TraceID().String()

	// Validate batch request using the new validation package
	if err := validation.ValidateBatchCreateTasks(req, traceID); err != nil {
		span.SetAttributes(attribute.String("validation.error", err.Error()))
		return nil, err
	}

	// Process each task
	var created []*todopb.Task
	var batchErrors []string

	for i, createReq := range req.Requests {
		task, err := s.CreateTask(ctx, createReq)
		if err != nil {
			// Collect errors for batch response
			batchErrors = append(batchErrors, fmt.Sprintf("Task %d: %s", i, err.Error()))
			continue
		}
		created = append(created, task)
	}

	// If all tasks failed, return error
	if len(created) == 0 && len(batchErrors) > 0 {
		return nil, errors.NewInternal("All batch operations failed", traceID, nil)
	}

	// Return partial success
	response := &todopb.BatchCreateTasksResponse{
		Tasks: created,
	}

	// Add partial errors to response metadata if any
	if len(batchErrors) > 0 {
		span.SetAttributes(
			attribute.Int("batch.total", len(req.Requests)),
			attribute.Int("batch.success", len(created)),
			attribute.Int("batch.failed", len(batchErrors)),
		)
	}

	return response, nil
}

// Helper methods

func (s *TodoService) handleRepositoryError(err error, traceID string) error {
	if repository.IsConnectionError(err) {
		return errors.NewServiceUnavailable("Unable to connect to the database. Please try again later.", traceID)
	}

	// Log internal error details
	span := trace.SpanFromContext(context.Background())
	if span != nil {
		span.RecordError(err)
	}

	return errors.NewInternal("An unexpected error occurred while processing your request", traceID, err)
}

func (s *TodoService) getUserFromContext(ctx context.Context) string {
	// In a real implementation, this would extract user info from auth context
	if user, ok := ctx.Value("user").(string); ok {
		return user
	}
	return "anonymous"
}

func (s *TodoService) canAccessTask(ctx context.Context, task *todopb.Task) bool {
	// In a real implementation, check if user can access this task
	user := s.getUserFromContext(ctx)
	return user == task.CreatedBy || user == "admin"
}

func (s *TodoService) canModifyTask(ctx context.Context, task *todopb.Task) bool {
	// In a real implementation, check if user can modify this task
	user := s.getUserFromContext(ctx)
	return user == task.CreatedBy || user == "admin"
}

func (s *TodoService) parseFilter(filter string) (map[string]interface{}, error) {
	// Simple filter parser - in production, use a proper parser
	parsed := make(map[string]interface{})

	if filter == "" {
		return parsed, nil
	}

	// Example: "status=COMPLETED AND priority=HIGH"
	parts := strings.Split(filter, " AND ")
	for _, part := range parts {
		kv := strings.Split(strings.TrimSpace(part), "=")
		if len(kv) != 2 {
			return nil, fmt.Errorf("invalid filter expression: %s", part)
		}

		key := strings.TrimSpace(kv[0])
		value := strings.Trim(strings.TrimSpace(kv[1]), "'\"")

		// Validate filter keys
		switch key {
		case "status", "priority", "created_by":
			parsed[key] = value
		default:
			return nil, fmt.Errorf("unknown filter field: %s", key)
		}
	}

	return parsed, nil
}

func (s *TodoService) applyFieldMask(existing, update *todopb.Task, mask *fieldmaskpb.FieldMask) *todopb.Task {
	result := *existing

	for _, path := range mask.Paths {
		switch path {
		case "title":
			result.Title = update.Title
		case "description":
			result.Description = update.Description
		case "status":
			result.Status = update.Status
		case "priority":
			result.Priority = update.Priority
		case "due_date":
			result.DueDate = update.DueDate
		case "tags":
			result.Tags = update.Tags
		}
	}
	return &result
}
