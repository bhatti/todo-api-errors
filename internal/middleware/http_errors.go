package middleware

import (
	"context"
	"encoding/json"
	"net/http"
	"runtime/debug"
	"time"

	errorspb "github.com/bhatti/todo-api-errors/api/proto/errors/v1"
	apperrors "github.com/bhatti/todo-api-errors/internal/errors"
	"github.com/google/uuid"
	"github.com/grpc-ecosystem/grpc-gateway/v2/runtime"
	"go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/encoding/protojson"
)

// HTTPErrorHandler handles errors for HTTP endpoints
func HTTPErrorHandler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Add trace ID to context
		traceID := r.Header.Get("X-Trace-ID")
		if traceID == "" {
			traceID = uuid.New().String()
		}
		ctx := context.WithValue(r.Context(), "traceID", traceID)
		r = r.WithContext(ctx)

		// Create response wrapper to intercept errors
		wrapped := &responseWriter{
			ResponseWriter: w,
			request:        r,
			traceID:        traceID,
		}

		// Handle panics
		defer func() {
			if err := recover(); err != nil {
				handlePanic(wrapped, err)
			}
		}()

		// Process request
		next.ServeHTTP(wrapped, r)
	})
}

// responseWriter wraps http.ResponseWriter to intercept errors
type responseWriter struct {
	http.ResponseWriter
	request    *http.Request
	traceID    string
	statusCode int
	written    bool
}

func (w *responseWriter) WriteHeader(code int) {
	if !w.written {
		w.statusCode = code
		w.ResponseWriter.WriteHeader(code)
		w.written = true
	}
}

func (w *responseWriter) Write(b []byte) (int, error) {
	if !w.written {
		w.WriteHeader(http.StatusOK)
	}
	return w.ResponseWriter.Write(b)
}

// handlePanic converts panics to proper error responses
func handlePanic(w *responseWriter, recovered interface{}) {
	// Log stack trace
	debug.PrintStack()

	appErr := apperrors.NewInternal("An unexpected error occurred. Please try again later.", w.traceID, nil)
	writeErrorResponse(w, appErr)
}

// CustomHTTPError handles gRPC gateway error responses
func CustomHTTPError(ctx context.Context, mux *runtime.ServeMux,
	marshaler runtime.Marshaler, w http.ResponseWriter, r *http.Request, err error) {

	// Extract trace ID
	traceID := r.Header.Get("X-Trace-ID")
	if traceID == "" {
		if span := trace.SpanFromContext(ctx); span.SpanContext().IsValid() {
			traceID = span.SpanContext().TraceID().String()
		} else {
			traceID = uuid.New().String()
		}
	}

	// Convert gRPC error to HTTP response
	st, _ := status.FromError(err)

	// Check if we have our custom error detail in status details
	for _, detail := range st.Details() {
		if errorDetail, ok := detail.(*errorspb.ErrorDetail); ok {
			// Update the error detail with current request context
			errorDetail.TraceId = traceID
			errorDetail.Instance = r.URL.Path

			// Convert to JSON and write response
			w.Header().Set("Content-Type", "application/problem+json")
			w.WriteHeader(runtime.HTTPStatusFromCode(st.Code()))

			// Create a simplified JSON response that matches RFC 7807
			response := map[string]interface{}{
				"type":      getTypeForCode(errorDetail.Code),
				"title":     errorDetail.Title,
				"status":    runtime.HTTPStatusFromCode(st.Code()),
				"detail":    errorDetail.Detail,
				"instance":  errorDetail.Instance,
				"traceId":   errorDetail.TraceId,
				"timestamp": errorDetail.Timestamp,
			}

			// Add field violations if present
			if len(errorDetail.FieldViolations) > 0 {
				violations := make([]map[string]interface{}, len(errorDetail.FieldViolations))
				for i, fv := range errorDetail.FieldViolations {
					violations[i] = map[string]interface{}{
						"field":   fv.Field,
						"code":    fv.Code,
						"message": fv.Description,
					}
				}
				response["errors"] = violations
			}

			// Add extensions if present
			if len(errorDetail.Extensions) > 0 {
				extensions := make(map[string]interface{})
				for k, v := range errorDetail.Extensions {
					// Convert Any to JSON
					if jsonBytes, err := protojson.Marshal(v); err == nil {
						var jsonData interface{}
						if err := json.Unmarshal(jsonBytes, &jsonData); err == nil {
							extensions[k] = jsonData
						}
					}
				}
				if len(extensions) > 0 {
					response["extensions"] = extensions
				}
			}

			if err := json.NewEncoder(w).Encode(response); err != nil {
				http.Error(w, `{"error": "Failed to encode error response"}`, 500)
			}
			return
		}
	}

	// Fallback: create new error response
	fallbackErr := apperrors.NewInternal(st.Message(), traceID, nil)
	fallbackErr.GRPCCode = st.Code()
	writeAppErrorResponse(w, fallbackErr, r.URL.Path)
}

// Helper functions
func getTypeForCode(code string) string {
	switch code {
	case errorspb.AppErrorCode_VALIDATION_FAILED.String():
		return "https://api.example.com/errors/validation-failed"
	case errorspb.AppErrorCode_RESOURCE_NOT_FOUND.String():
		return "https://api.example.com/errors/resource-not-found"
	case errorspb.AppErrorCode_RESOURCE_CONFLICT.String():
		return "https://api.example.com/errors/resource-conflict"
	case errorspb.AppErrorCode_PERMISSION_DENIED.String():
		return "https://api.example.com/errors/permission-denied"
	case errorspb.AppErrorCode_INTERNAL_ERROR.String():
		return "https://api.example.com/errors/internal-error"
	case errorspb.AppErrorCode_SERVICE_UNAVAILABLE.String():
		return "https://api.example.com/errors/service-unavailable"
	default:
		return "https://api.example.com/errors/unknown"
	}
}

func writeErrorResponse(w http.ResponseWriter, err error) {
	if appErr, ok := err.(*apperrors.AppError); ok {
		writeAppErrorResponse(w, appErr, "")
	} else {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func writeAppErrorResponse(w http.ResponseWriter, appErr *apperrors.AppError, instance string) {
	statusCode := runtime.HTTPStatusFromCode(appErr.GRPCCode)

	response := map[string]interface{}{
		"type":      getTypeForCode(appErr.AppCode.String()),
		"title":     appErr.Title,
		"status":    statusCode,
		"detail":    appErr.Detail,
		"traceId":   appErr.TraceID,
		"timestamp": time.Now(),
	}

	if instance != "" {
		response["instance"] = instance
	}

	if len(appErr.FieldViolations) > 0 {
		violations := make([]map[string]interface{}, len(appErr.FieldViolations))
		for i, fv := range appErr.FieldViolations {
			violations[i] = map[string]interface{}{
				"field":   fv.Field,
				"code":    fv.Code,
				"message": fv.Description,
			}
		}
		response["errors"] = violations
	}

	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(response)
}
