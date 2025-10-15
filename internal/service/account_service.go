package service

import (
	"context"
	"fmt"
	"sync"
	"time"

	pii "github.com/bhatti/todo-api-errors/api/proto/pii/v1"
	"github.com/google/uuid"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// AccountService implements the account CRUD operations
// This is a demo service to showcase PII handling
type AccountService struct {
	pii.UnimplementedAccountServiceServer
	mu       sync.RWMutex
	accounts map[string]*pii.Account
}

// NewAccountService creates a new account service
func NewAccountService() *AccountService {
	return &AccountService{
		accounts: make(map[string]*pii.Account),
	}
}

// CreateAccount creates a new account
func (s *AccountService) CreateAccount(ctx context.Context, req *pii.CreateAccountRequest) (*pii.Account, error) {
	if req.Account == nil {
		return nil, status.Error(codes.InvalidArgument, "account is required")
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	// Generate ID if not provided
	if req.Account.Id == "" {
		req.Account.Id = uuid.New().String()
	}

	// Check for duplicate
	if _, exists := s.accounts[req.Account.Id]; exists {
		return nil, status.Errorf(codes.AlreadyExists, "account %s already exists", req.Account.Id)
	}

	// Set timestamps
	now := timestamppb.Now()
	req.Account.CreatedAt = now
	req.Account.UpdatedAt = now

	// Store account
	s.accounts[req.Account.Id] = req.Account

	// Log PII access (in production, this would go to audit log)
	s.logPIIAccess(ctx, "CREATE", req.Account.Id, "HIGH")

	return req.Account, nil
}

// GetAccount retrieves an account by ID
func (s *AccountService) GetAccount(ctx context.Context, req *pii.GetAccountRequest) (*pii.Account, error) {
	if req.Id == "" {
		return nil, status.Error(codes.InvalidArgument, "id is required")
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	account, exists := s.accounts[req.Id]
	if !exists {
		return nil, status.Errorf(codes.NotFound, "account %s not found", req.Id)
	}

	// Log PII access
	s.logPIIAccess(ctx, "READ", req.Id, "HIGH")

	// If include_sensitive_data is false, we could mask sensitive fields
	// For demo purposes, we'll return the full account
	if !req.IncludeSensitiveData {
		// In production, we would mask fields marked as HIGH sensitivity
		// This is where PII masking logic would be applied
		return s.maskSensitiveData(account), nil
	}

	return account, nil
}

// UpdateAccount updates an existing account
func (s *AccountService) UpdateAccount(ctx context.Context, req *pii.UpdateAccountRequest) (*pii.Account, error) {
	if req.Account == nil || req.Account.Id == "" {
		return nil, status.Error(codes.InvalidArgument, "account with id is required")
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	existing, exists := s.accounts[req.Account.Id]
	if !exists {
		return nil, status.Errorf(codes.NotFound, "account %s not found", req.Account.Id)
	}

	// Apply updates based on field mask
	if req.UpdateMask != nil && len(req.UpdateMask.Paths) > 0 {
		s.applyFieldMask(existing, req.Account, req.UpdateMask.Paths)
	} else {
		// Full update
		req.Account.CreatedAt = existing.CreatedAt
		s.accounts[req.Account.Id] = req.Account
		existing = req.Account
	}

	// Update timestamp
	existing.UpdatedAt = timestamppb.Now()

	// Log PII access
	s.logPIIAccess(ctx, "UPDATE", req.Account.Id, "HIGH")

	return existing, nil
}

// DeleteAccount deletes an account
func (s *AccountService) DeleteAccount(ctx context.Context, req *pii.DeleteAccountRequest) (*emptypb.Empty, error) {
	if req.Id == "" {
		return nil, status.Error(codes.InvalidArgument, "id is required")
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.accounts[req.Id]; !exists {
		return nil, status.Errorf(codes.NotFound, "account %s not found", req.Id)
	}

	if req.HardDelete {
		// Permanently delete
		delete(s.accounts, req.Id)
		s.logPIIAccess(ctx, "HARD_DELETE", req.Id, "LOW")
	} else {
		// Soft delete - just mark as closed
		s.accounts[req.Id].Status = pii.AccountStatus_CLOSED
		s.accounts[req.Id].UpdatedAt = timestamppb.Now()
		s.logPIIAccess(ctx, "SOFT_DELETE", req.Id, "LOW")
	}

	return &emptypb.Empty{}, nil
}

// ListAccounts lists all accounts with pagination
func (s *AccountService) ListAccounts(ctx context.Context, req *pii.ListAccountsRequest) (*pii.ListAccountsResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// Simple pagination (in production, use proper cursor-based pagination)
	pageSize := req.PageSize
	if pageSize <= 0 {
		pageSize = 10
	}
	if pageSize > 100 {
		pageSize = 100
	}

	var accounts []*pii.Account
	for _, account := range s.accounts {
		// Apply filter if provided
		if req.Filter != "" && !s.matchesFilter(account, req.Filter) {
			continue
		}
		accounts = append(accounts, account)
	}

	// Log PII access
	s.logPIIAccess(ctx, "LIST", fmt.Sprintf("count=%d", len(accounts)), "HIGH")

	// Simple pagination
	start := 0
	if req.PageToken != "" {
		// In production, decode proper page token
		start = len(req.PageToken) // Simplified for demo
	}

	end := start + int(pageSize)
	if end > len(accounts) {
		end = len(accounts)
	}

	var nextPageToken string
	if end < len(accounts) {
		nextPageToken = fmt.Sprintf("page_%d", end)
	}

	return &pii.ListAccountsResponse{
		Accounts:      accounts[start:end],
		NextPageToken: nextPageToken,
		TotalCount:    int32(len(accounts)),
	}, nil
}

// SearchAccounts searches accounts by PII fields
func (s *AccountService) SearchAccounts(ctx context.Context, req *pii.SearchAccountsRequest) (*pii.SearchAccountsResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var matches []*pii.Account

	// Search through accounts (simplified for demo)
	for _, account := range s.accounts {
		matched := false

		// Check each search field
		if req.Name != "" && (account.FirstName == req.Name || account.LastName == req.Name) {
			matched = true
		}
		if req.Email != "" && (account.Email == req.Email || account.PersonalEmail == req.Email) {
			matched = true
		}
		if req.Phone != "" && (account.Phone == req.Phone || account.MobilePhone == req.Phone) {
			matched = true
		}
		if req.Ssn != "" && account.Ssn == req.Ssn {
			matched = true
			// Log HIGH sensitivity PII search
			s.logPIIAccess(ctx, "SEARCH_SSN", account.Id, "HIGH")
		}
		if req.DateOfBirth != "" && account.DateOfBirth == req.DateOfBirth {
			matched = true
		}

		if matched {
			matches = append(matches, account)
		}
	}

	// Log PII access
	s.logPIIAccess(ctx, "SEARCH", fmt.Sprintf("results=%d", len(matches)), "HIGH")

	// Apply pagination
	pageSize := req.PageSize
	if pageSize <= 0 {
		pageSize = 10
	}
	if pageSize > 100 {
		pageSize = 100
	}

	end := int(pageSize)
	if end > len(matches) {
		end = len(matches)
	}

	var nextPageToken string
	if end < len(matches) {
		nextPageToken = fmt.Sprintf("search_%d", end)
	}

	return &pii.SearchAccountsResponse{
		Accounts:      matches[:end],
		NextPageToken: nextPageToken,
		TotalMatches:  int32(len(matches)),
	}, nil
}

// Helper methods

func (s *AccountService) maskSensitiveData(account *pii.Account) *pii.Account {
	// Create a copy to avoid modifying the original
	masked := *account

	// Mask HIGH sensitivity fields
	if masked.Ssn != "" {
		masked.Ssn = "XXX-XX-" + lastN(masked.Ssn, 4)
	}
	if masked.TaxId != "" {
		masked.TaxId = "XX-XXX" + lastN(masked.TaxId, 4)
	}
	if masked.PassportNumber != "" {
		masked.PassportNumber = "XXXX" + lastN(masked.PassportNumber, 4)
	}
	if masked.DriversLicense != "" {
		masked.DriversLicense = "XXXX" + lastN(masked.DriversLicense, 4)
	}
	if masked.BankAccountNumber != "" {
		masked.BankAccountNumber = "****" + lastN(masked.BankAccountNumber, 4)
	}
	if masked.CreditCardNumber != "" {
		masked.CreditCardNumber = "****-****-****-" + lastN(masked.CreditCardNumber, 4)
	}
	masked.CreditCardCvv = "***"
	masked.PasswordHash = "********"
	masked.SecurityAnswer = "********"
	masked.ApiKey = "****"
	masked.AccessToken = "****"

	// Mask MEDIUM sensitivity fields partially
	if masked.Email != "" {
		masked.Email = maskEmail(masked.Email)
	}
	if masked.PersonalEmail != "" {
		masked.PersonalEmail = maskEmail(masked.PersonalEmail)
	}
	if masked.Phone != "" {
		masked.Phone = maskPhone(masked.Phone)
	}
	if masked.MobilePhone != "" {
		masked.MobilePhone = maskPhone(masked.MobilePhone)
	}

	return &masked
}

func (s *AccountService) matchesFilter(account *pii.Account, filter string) bool {
	// Simplified filter matching for demo
	// In production, use proper filter parsing
	if filter == "status=ACTIVE" {
		return account.Status == pii.AccountStatus_ACTIVE
	}
	return true
}

func (s *AccountService) applyFieldMask(target, source *pii.Account, paths []string) {
	// Apply field mask updates
	for _, path := range paths {
		switch path {
		case "first_name":
			target.FirstName = source.FirstName
		case "last_name":
			target.LastName = source.LastName
		case "email":
			target.Email = source.Email
		case "phone":
			target.Phone = source.Phone
		case "home_address":
			target.HomeAddress = source.HomeAddress
		// Add more fields as needed
		}
	}
}

func (s *AccountService) logPIIAccess(ctx context.Context, action, resourceID, sensitivity string) {
	// In production, this would write to an audit log
	// For demo, we'll just print to stdout
	timestamp := time.Now().Format(time.RFC3339)
	fmt.Printf("[PII_AUDIT] %s | Action=%s | Resource=%s | Sensitivity=%s | Context=%v\n",
		timestamp, action, resourceID, sensitivity, ctx)
}

// Utility functions

func lastN(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[len(s)-n:]
}

func maskEmail(email string) string {
	// Simple email masking: show first 2 chars and domain
	if len(email) < 3 {
		return "***"
	}
	atIndex := -1
	for i, ch := range email {
		if ch == '@' {
			atIndex = i
			break
		}
	}
	if atIndex < 0 {
		return email[:2] + "***"
	}
	return email[:2] + "***" + email[atIndex:]
}

func maskPhone(phone string) string {
	// Simple phone masking: show last 4 digits
	if len(phone) <= 4 {
		return phone
	}
	return "XXX-XXX-" + lastN(phone, 4)
}