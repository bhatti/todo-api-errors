package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

func main() {
	client := &http.Client{Timeout: 10 * time.Second}
	baseURL := "http://localhost:8080/v1"

	// Test 1: Create task with validation errors
	fmt.Println("Test 1: Validation Errors")
	testValidationErrors(client, baseURL)

	// Test 2: Get non-existent task
	fmt.Println("\nTest 2: Not Found Error")
	testNotFound(client, baseURL)

	// Test 3: Create duplicate task
	fmt.Println("\nTest 3: Conflict Error")
	testConflict(client, baseURL)

	// Test 4: Batch create with partial failures
	fmt.Println("\nTest 4: Batch Create with Partial Failures")
	testBatchCreate(client, baseURL)
}

func testValidationErrors(client *http.Client, baseURL string) {
	payload := map[string]interface{}{
		"task": map[string]interface{}{
			"title":       "",                                                // Empty title
			"description": string(make([]byte, 1001)),                        // Too long
			"tags":        []string{"INVALID TAG", "valid-tag", "valid-tag"}, // Invalid format and duplicate
		},
	}

	resp := makeRequest(client, "POST", baseURL+"/tasks", payload)
	printResponse(resp)
}

func testNotFound(client *http.Client, baseURL string) {
	resp := makeRequest(client, "GET", baseURL+"/tasks/non-existent", nil)
	printResponse(resp)
}

func testConflict(client *http.Client, baseURL string) {
	// Create first task
	payload := map[string]interface{}{
		"task": map[string]interface{}{
			"title": "Unique Task Title",
		},
	}
	makeRequest(client, "POST", baseURL+"/tasks", payload)

	// Try to create duplicate
	resp := makeRequest(client, "POST", baseURL+"/tasks", payload)
	printResponse(resp)
}

func testBatchCreate(client *http.Client, baseURL string) {
	payload := map[string]interface{}{
		"requests": []map[string]interface{}{
			{"task": map[string]interface{}{"title": "Valid Task 1"}},
			{"task": map[string]interface{}{"title": ""}}, // Invalid
			{"task": map[string]interface{}{"title": "Valid Task 2"}},
			{"task": nil}, // Invalid
		},
	}

	resp := makeRequest(client, "POST", baseURL+"/tasks:batchCreate", payload)
	printResponse(resp)
}

func makeRequest(client *http.Client, method, url string, payload interface{}) *http.Response {
	var body io.Reader
	if payload != nil {
		data, _ := json.Marshal(payload)
		body = bytes.NewBuffer(data)
	}

	req, _ := http.NewRequest(method, url, body)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Trace-ID", fmt.Sprintf("test-%d", time.Now().Unix()))

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("Request failed: %v\n", err)
		return nil
	}

	return resp
}

func printResponse(resp *http.Response) {
	if resp == nil {
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	fmt.Printf("Status: %d %s\n", resp.StatusCode, resp.Status)
	fmt.Printf("Headers:\n")
	for key, values := range resp.Header {
		fmt.Printf("  %s: %s\n", key, values[0])
	}

	var prettyJSON bytes.Buffer
	if err := json.Indent(&prettyJSON, body, "", "  "); err == nil {
		fmt.Printf("Body:\n%s\n", prettyJSON.String())
	} else {
		fmt.Printf("Body:\n%s\n", body)
	}
}
