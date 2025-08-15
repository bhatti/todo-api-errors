package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	todopb "github.com/bhatti/todo-api-errors/api/proto/todo/v1"
	"github.com/bhatti/todo-api-errors/internal/middleware"
	"github.com/bhatti/todo-api-errors/internal/monitoring"
	"github.com/bhatti/todo-api-errors/internal/repository"
	"github.com/bhatti/todo-api-errors/internal/service"

	"github.com/grpc-ecosystem/grpc-gateway/v2/runtime"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/reflection"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/encoding/protojson"
)

func main() {
	// Initialize monitoring
	if err := monitoring.InitOpenTelemetryMetrics(); err != nil {
		log.Printf("Failed to initialize OpenTelemetry metrics: %v", err)
		// Continue without OpenTelemetry - Prometheus will still work
	}

	// Initialize repository
	repo := repository.NewInMemoryRepository()

	// Initialize service
	todoService, err := service.NewTodoService(repo)
	if err != nil {
		log.Fatalf("Failed to create service: %v", err)
	}

	// Start gRPC server
	grpcPort := ":50051"
	go func() {
		if err := startGRPCServer(grpcPort, todoService); err != nil {
			log.Fatalf("Failed to start gRPC server: %v", err)
		}
	}()

	// Start HTTP gateway
	httpPort := ":8080"
	go func() {
		if err := startHTTPGateway(httpPort, grpcPort); err != nil {
			log.Fatalf("Failed to start HTTP gateway: %v", err)
		}
	}()

	// Start metrics server
	go func() {
		http.Handle("/metrics", promhttp.Handler())
		if err := http.ListenAndServe(":9090", nil); err != nil {
			log.Printf("Failed to start metrics server: %v", err)
		}
	}()

	log.Printf("TODO API server started")
	log.Printf("gRPC server listening on %s", grpcPort)
	log.Printf("HTTP gateway listening on %s", httpPort)
	log.Printf("Metrics available at :9090/metrics")

	// Wait for interrupt signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	log.Println("Shutting down...")
}

func startGRPCServer(port string, todoService todopb.TodoServiceServer) error {
	lis, err := net.Listen("tcp", port)
	if err != nil {
		return fmt.Errorf("failed to listen: %w", err)
	}

	// Create gRPC server with interceptors - now using the new UnaryErrorInterceptor
	opts := []grpc.ServerOption{
		grpc.ChainUnaryInterceptor(
			middleware.UnaryErrorInterceptor, // Using new protobuf-based error interceptor
			loggingInterceptor(),
			recoveryInterceptor(),
		),
	}

	server := grpc.NewServer(opts...)

	// Register service
	todopb.RegisterTodoServiceServer(server, todoService)

	// Register reflection for debugging
	reflection.Register(server)

	return server.Serve(lis)
}

func startHTTPGateway(httpPort, grpcPort string) error {
	ctx := context.Background()

	// Create gRPC connection
	conn, err := grpc.DialContext(
		ctx,
		"localhost"+grpcPort,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return fmt.Errorf("failed to dial gRPC server: %w", err)
	}

	// Create gateway mux with custom error handler
	mux := runtime.NewServeMux(
		runtime.WithErrorHandler(middleware.CustomHTTPError), // Using new protobuf-based error handler
		runtime.WithMarshalerOption(runtime.MIMEWildcard, &runtime.JSONPb{
			MarshalOptions: protojson.MarshalOptions{
				UseProtoNames:   true,
				EmitUnpopulated: false,
			},
			UnmarshalOptions: protojson.UnmarshalOptions{
				DiscardUnknown: true,
			},
		}),
	)

	// Register service handler
	if err := todopb.RegisterTodoServiceHandler(ctx, mux, conn); err != nil {
		return fmt.Errorf("failed to register service handler: %w", err)
	}

	// Create HTTP server with middleware
	handler := middleware.HTTPErrorHandler( // Using new protobuf-based HTTP error handler
		corsMiddleware(
			authMiddleware(
				loggingHTTPMiddleware(mux),
			),
		),
	)

	server := &http.Server{
		Addr:         httpPort,
		Handler:      handler,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	return server.ListenAndServe()
}

// Middleware implementations

func loggingInterceptor() grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		start := time.Now()

		// Call handler
		resp, err := handler(ctx, req)

		// Log request
		duration := time.Since(start)
		statusCode := "OK"
		if err != nil {
			statusCode = status.Code(err).String()
		}

		log.Printf("gRPC: %s %s %s %v", info.FullMethod, statusCode, duration, err)

		return resp, err
	}
}

func recoveryInterceptor() grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (resp interface{}, err error) {
		defer func() {
			if r := recover(); r != nil {
				log.Printf("Recovered from panic: %v", r)
				monitoring.RecordPanicRecovery(ctx)
				err = status.Error(codes.Internal, "Internal server error")
			}
		}()

		return handler(ctx, req)
	}
}

func loggingHTTPMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		// Wrap response writer to capture status
		wrapped := &statusResponseWriter{ResponseWriter: w, statusCode: http.StatusOK}

		// Process request
		next.ServeHTTP(wrapped, r)

		// Log request
		duration := time.Since(start)
		log.Printf("HTTP: %s %s %d %v", r.Method, r.URL.Path, wrapped.statusCode, duration)
	})
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Trace-ID")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Simple auth for demo - in production use proper authentication
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" {
			authHeader = "Bearer anonymous"
		}

		// Extract user from token
		user := "anonymous"
		if len(authHeader) > 7 && authHeader[:7] == "Bearer " {
			user = authHeader[7:]
		}

		// Add user to context
		ctx := context.WithValue(r.Context(), "user", user)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

type statusResponseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (w *statusResponseWriter) WriteHeader(code int) {
	w.statusCode = code
	w.ResponseWriter.WriteHeader(code)
}
