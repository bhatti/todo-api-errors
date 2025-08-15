package middleware

import (
	"context"
	"errors"
	"log"

	apperrors "github.com/bhatti/todo-api-errors/internal/errors"
	"google.golang.org/grpc"
	"google.golang.org/grpc/status"
)

// UnaryErrorInterceptor translates application errors into gRPC statuses.
func UnaryErrorInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
	resp, err := handler(ctx, req)
	if err == nil {
		return resp, nil
	}

	var appErr *apperrors.AppError
	if errors.As(err, &appErr) {
		if appErr.CausedBy != nil {
			log.Printf("ERROR: %s, Original cause: %v", appErr.Title, appErr.CausedBy)
		}
		return nil, appErr.ToGRPCStatus().Err()
	}

	if _, ok := status.FromError(err); ok {
		return nil, err // Already a gRPC status
	}

	log.Printf("UNEXPECTED ERROR: %v", err)
	return nil, apperrors.NewInternal("An unexpected error occurred", "", err).ToGRPCStatus().Err()
}
