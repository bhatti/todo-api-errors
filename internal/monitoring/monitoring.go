package monitoring

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
)

var (
	// Error metrics
	errorCounter = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "todo_api_errors_total",
			Help: "Total number of API errors by type and status",
		},
		[]string{"error_type", "status_code", "method", "endpoint"},
	)

	// Validation error metrics
	validationErrorCounter = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "todo_api_validation_errors_total",
			Help: "Total number of validation errors by field and code",
		},
		[]string{"field", "code", "endpoint"},
	)

	// Error response time
	errorResponseTime = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "todo_api_error_response_time_seconds",
			Help:    "Time taken to generate error responses",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"error_type"},
	)

	// Recovery metrics
	panicRecoveryCounter = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "todo_api_panic_recovery_total",
			Help: "Total number of recovered panics",
		},
	)
)

// OpenTelemetry metrics instruments
var (
	otelMeter                 metric.Meter
	otelErrorCounter          metric.Int64Counter
	otelValidationCounter     metric.Int64Counter
	otelResponseTimeHistogram metric.Float64Histogram
	otelPanicCounter          metric.Int64Counter
	otelInitOnce              sync.Once
)

// InitOpenTelemetryMetrics initializes OpenTelemetry metrics instruments
func InitOpenTelemetryMetrics() error {
	var err error
	otelInitOnce.Do(func() {
		// Get the global meter provider
		otelMeter = otel.Meter("todo-api-errors")

		// Create error counter
		otelErrorCounter, err = otelMeter.Int64Counter(
			"api.errors.total",
			metric.WithDescription("Total number of API errors"),
		)
		if err != nil {
			return
		}

		// Create validation error counter
		otelValidationCounter, err = otelMeter.Int64Counter(
			"api.validation_errors.total",
			metric.WithDescription("Total number of validation errors"),
		)
		if err != nil {
			return
		}

		// Create response time histogram
		otelResponseTimeHistogram, err = otelMeter.Float64Histogram(
			"api.error_response_time.seconds",
			metric.WithDescription("Time taken to generate error responses"),
		)
		if err != nil {
			return
		}

		// Create panic recovery counter
		otelPanicCounter, err = otelMeter.Int64Counter(
			"api.panic_recovery.total",
			metric.WithDescription("Total number of recovered panics"),
		)
	})
	return err
}

// RecordError records error metrics
func RecordError(ctx context.Context, errorType string, statusCode int, method, endpoint string) {
	// Record Prometheus metrics
	errorCounter.WithLabelValues(errorType, fmt.Sprintf("%d", statusCode), method, endpoint).Inc()

	// Record OpenTelemetry metrics (if initialized)
	if otelErrorCounter != nil {
		otelErrorCounter.Add(ctx, 1,
			metric.WithAttributes(
				attribute.String("error.type", errorType),
				attribute.Int("http.status_code", statusCode),
				attribute.String("http.method", method),
				attribute.String("http.route", endpoint),
			),
		)
	}
}

// RecordValidationError records validation error metrics
func RecordValidationError(ctx context.Context, field, code, endpoint string) {
	// Record Prometheus metrics
	validationErrorCounter.WithLabelValues(field, code, endpoint).Inc()

	// Record OpenTelemetry metrics (if initialized)
	if otelValidationCounter != nil {
		otelValidationCounter.Add(ctx, 1,
			metric.WithAttributes(
				attribute.String("validation.field", field),
				attribute.String("validation.code", code),
				attribute.String("http.route", endpoint),
			),
		)
	}
}

// RecordErrorResponseTime records the time taken to generate an error response
func RecordErrorResponseTime(ctx context.Context, errorType string, duration time.Duration) {
	// Record Prometheus metrics
	errorResponseTime.WithLabelValues(errorType).Observe(duration.Seconds())

	// Record OpenTelemetry metrics (if initialized)
	if otelResponseTimeHistogram != nil {
		otelResponseTimeHistogram.Record(ctx, duration.Seconds(),
			metric.WithAttributes(
				attribute.String("error.type", errorType),
			),
		)
	}
}

// RecordPanicRecovery records panic recovery events
func RecordPanicRecovery(ctx context.Context) {
	// Record Prometheus metrics
	panicRecoveryCounter.Inc()

	// Record OpenTelemetry metrics (if initialized)
	if otelPanicCounter != nil {
		otelPanicCounter.Add(ctx, 1)
	}
}

// RecordValidationErrors records multiple validation errors at once
func RecordValidationErrors(ctx context.Context, validationErrors []ValidationError, endpoint string) {
	for _, ve := range validationErrors {
		RecordValidationError(ctx, ve.Field, ve.Code, endpoint)
	}
}

// ValidationError represents a validation error for metrics
type ValidationError struct {
	Field string
	Code  string
}
