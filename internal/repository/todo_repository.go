package repository

import (
	"context"
	"errors"
	todopb "github.com/bhatti/todo-api-errors/api/proto/todo/v1"
	"sort"
	"strings"
	"sync"
)

// Common errors
var (
	ErrNotFound      = errors.New("not found")
	ErrAlreadyExists = errors.New("already exists")
	ErrConnection    = errors.New("connection error")
)

// TodoRepository defines the interface for task storage
type TodoRepository interface {
	CreateTask(ctx context.Context, task *todopb.Task) error
	GetTask(ctx context.Context, id string) (*todopb.Task, error)
	GetTaskByTitle(ctx context.Context, title string) (*todopb.Task, error)
	UpdateTask(ctx context.Context, task *todopb.Task) error
	DeleteTask(ctx context.Context, id string) error
	ListTasks(ctx context.Context, opts ListOptions) ([]*todopb.Task, string, error)
	CountTasks(ctx context.Context, filter map[string]interface{}, userID string) (int, error)
}

// ListOptions contains options for listing tasks
type ListOptions struct {
	PageSize  int
	PageToken string
	Filter    map[string]interface{}
	OrderBy   string
	UserID    string
}

// InMemoryRepository is a simple in-memory implementation
type InMemoryRepository struct {
	mu    sync.RWMutex
	tasks map[string]*todopb.Task
	index map[string]string // title -> id index
}

// NewInMemoryRepository creates a new in-memory repository
func NewInMemoryRepository() *InMemoryRepository {
	return &InMemoryRepository{
		tasks: make(map[string]*todopb.Task),
		index: make(map[string]string),
	}
}

func (r *InMemoryRepository) CreateTask(_ context.Context, task *todopb.Task) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	id := extractID(task.Name)

	// Check if already exists
	if _, exists := r.tasks[id]; exists {
		return ErrAlreadyExists
	}

	// Check title uniqueness
	if existingID, exists := r.index[task.Title]; exists && existingID != id {
		return ErrAlreadyExists
	}

	// Store task
	r.tasks[id] = task
	r.index[task.Title] = id

	return nil
}

func (r *InMemoryRepository) GetTask(_ context.Context, id string) (*todopb.Task, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	task, exists := r.tasks[id]
	if !exists {
		return nil, ErrNotFound
	}

	return task, nil
}

func (r *InMemoryRepository) GetTaskByTitle(ctx context.Context, title string) (*todopb.Task, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	id, exists := r.index[title]
	if !exists {
		return nil, ErrNotFound
	}

	return r.GetTask(ctx, id)
}

func (r *InMemoryRepository) UpdateTask(_ context.Context, task *todopb.Task) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	id := extractID(task.Name)

	existing, exists := r.tasks[id]
	if !exists {
		return ErrNotFound
	}

	// Update title index if changed
	if existing.Title != task.Title {
		delete(r.index, existing.Title)

		// Check new title uniqueness
		if existingID, exists := r.index[task.Title]; exists && existingID != id {
			return ErrAlreadyExists
		}

		r.index[task.Title] = id
	}

	r.tasks[id] = task
	return nil
}

func (r *InMemoryRepository) DeleteTask(_ context.Context, id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	task, exists := r.tasks[id]
	if !exists {
		return ErrNotFound
	}

	delete(r.tasks, id)
	delete(r.index, task.Title)

	return nil
}

func (r *InMemoryRepository) ListTasks(_ context.Context, opts ListOptions) ([]*todopb.Task, string, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	// Filter tasks
	var filtered []*todopb.Task
	for _, task := range r.tasks {
		if r.matchesFilter(task, opts.Filter, opts.UserID) {
			filtered = append(filtered, task)
		}
	}

	// Sort tasks
	sortTasks(filtered, opts.OrderBy)

	// Paginate
	start := 0
	if opts.PageToken != "" {
		// In production, decode proper page token
		for i, task := range filtered {
			if extractID(task.Name) == opts.PageToken {
				start = i + 1
				break
			}
		}
	}

	end := start + opts.PageSize
	if end > len(filtered) {
		end = len(filtered)
	}

	var nextToken string
	if end < len(filtered) {
		nextToken = extractID(filtered[end-1].Name)
	}

	return filtered[start:end], nextToken, nil
}

func (r *InMemoryRepository) CountTasks(_ context.Context, filter map[string]interface{}, userID string) (int, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	count := 0
	for _, task := range r.tasks {
		if r.matchesFilter(task, filter, userID) {
			count++
		}
	}

	return count, nil
}

// Helper functions

func (r *InMemoryRepository) matchesFilter(task *todopb.Task, filter map[string]interface{}, userID string) bool {
	// Check user access
	if userID != "" && task.CreatedBy != userID && userID != "admin" {
		return false
	}

	// Apply filters
	for key, value := range filter {
		switch key {
		case "status":
			if task.Status.String() != value.(string) {
				return false
			}
		case "priority":
			if task.Priority.String() != value.(string) {
				return false
			}
		case "created_by":
			if task.CreatedBy != value.(string) {
				return false
			}
		}
	}

	return true
}

func extractID(name string) string {
	parts := strings.Split(name, "/")
	if len(parts) == 2 {
		return parts[1]
	}
	return name
}

func sortTasks(tasks []*todopb.Task, orderBy string) {
	// Simple sorting implementation
	sort.Slice(tasks, func(i, j int) bool {
		switch orderBy {
		case "create_time":
			return tasks[i].CreateTime.AsTime().Before(tasks[j].CreateTime.AsTime())
		case "-create_time":
			return tasks[i].CreateTime.AsTime().After(tasks[j].CreateTime.AsTime())
		case "due_date":
			if tasks[i].DueDate == nil {
				return false
			}
			if tasks[j].DueDate == nil {
				return true
			}
			return tasks[i].DueDate.AsTime().Before(tasks[j].DueDate.AsTime())
		default:
			return tasks[i].Title < tasks[j].Title
		}
	})
}

func IsNotFound(err error) bool {
	return errors.Is(err, ErrNotFound)
}

func IsAlreadyExists(err error) bool {
	return errors.Is(err, ErrAlreadyExists)
}

func IsConnectionError(err error) bool {
	return errors.Is(err, ErrConnection)
}
