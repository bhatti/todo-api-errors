# PII Classification Rules Reference

This document defines the expected PII classification rules that the automation should follow when analyzing proto files and suggesting annotations.

## Sensitivity Levels

### PUBLIC (Level 1)
- Non-sensitive, public information
- Can be freely shared without privacy concerns
- Examples:
  - Company names
  - Public product information
  - Non-personal metadata
  - System status enums

### LOW (Level 2)
- Personal data with minimal sensitivity
- Generally visible in professional contexts
- Examples:
  - Names (first, last, middle)
  - Job titles
  - Work email addresses
  - Work phone numbers
  - Work addresses
  - Employer names
  - Gender (when not medical context)
  - City, state, country (without street address)

### MEDIUM (Level 3)
- Moderate sensitivity personal data
- Requires protection but not highest level
- Examples:
  - Personal email addresses
  - Personal phone numbers
  - Home addresses (full)
  - Date of birth
  - Account numbers (non-financial)
  - Employee IDs
  - Usernames
  - IP addresses
  - Device IDs
  - Geolocation data
  - Postal/ZIP codes
  - Metadata that might contain PII

### HIGH (Level 4)
- Highly sensitive data requiring maximum protection
- Must be encrypted and access-controlled
- Examples:
  - Social Security Numbers (SSN)
  - Tax IDs (EIN, ITIN)
  - Passport numbers
  - Driver's license numbers
  - National ID numbers
  - Bank account numbers
  - Credit card numbers (including CVV)
  - Routing numbers
  - Medical record numbers
  - Health insurance IDs
  - Medical conditions
  - Prescriptions
  - Passwords (even hashed)
  - Security questions/answers
  - API keys and tokens
  - Salary/income information
  - Credit scores
  - Financial account details

## Classification Rules

### 1. Field-Level Classification
- Every field containing PII must have `(pii.v1.sensitivity)` annotation
- Fields should also have `(pii.v1.pii_type)` when applicable
- Use the most specific PII type available

### 2. Message-Level Classification
- Messages containing any PII fields should have `(pii.v1.message_sensitivity)`
- Use the highest sensitivity level among all fields in the message

### 3. Method-Level Classification
- RPC methods should have `(pii.v1.method_sensitivity)` based on data they handle
- Methods handling any PII should have `(pii.v1.audit_pii_access) = true`
- Use the highest sensitivity level of request/response messages

### 4. Composite Fields
- Repeated fields inherit the sensitivity of their element type
- Map fields should be classified based on potential content
- Nested messages maintain their own sensitivity levels

### 5. Special Cases
- Timestamps (created_at, updated_at): Generally not PII
- IDs depend on context:
  - Internal system IDs: LOW
  - Account/Customer IDs: LOW to MEDIUM
  - Government IDs: HIGH
- Addresses:
  - Work address: LOW
  - Home/mailing address: MEDIUM
  - Just city/state/country: LOW
  - Full street address: MEDIUM
- Emails:
  - Work email: LOW
  - Personal email: MEDIUM
- Financial data: Always HIGH
- Medical data: Always HIGH
- Authentication data: Always HIGH (except username: MEDIUM)

## Method Sensitivity Guidelines

### HIGH Sensitivity Methods
- CreateAccount - handles full account data
- GetAccount - returns full account data
- UpdateAccount - modifies sensitive data
- ListAccounts - returns multiple accounts
- SearchAccounts - queries using PII

### MEDIUM Sensitivity Methods
- Methods that only handle partial PII
- Read-only operations with limited fields

### LOW Sensitivity Methods
- DeleteAccount - typically only uses ID
- Status checks
- Operations on non-PII data

## Audit Requirements

All methods that:
1. Access any PII (read or write)
2. Perform searches using PII
3. Export or list records containing PII

Should have: `option (pii.v1.audit_pii_access) = true;`

## Validation Checklist

When reviewing proto files for PII:

1. ✓ Check every string field for potential PII
2. ✓ Check numeric fields for IDs, scores, financial amounts
3. ✓ Check bytes fields for encrypted/encoded PII
4. ✓ Review field names for PII indicators
5. ✓ Consider composite data in maps and repeated fields
6. ✓ Verify message-level annotations match contained fields
7. ✓ Ensure method annotations reflect handled data
8. ✓ Confirm audit flags on PII-handling methods

## Common Patterns to Detect

### Personal Identifiers
- Fields containing: name, firstname, lastname, surname
- Fields containing: ssn, social_security, tax_id
- Fields containing: passport, license, national_id

### Contact Information
- Fields containing: email, mail, phone, mobile, tel
- Fields containing: address, street, city, postal, zip

### Financial Information
- Fields containing: account, bank, credit, card, routing
- Fields containing: income, salary, score, amount

### Medical Information
- Fields containing: medical, health, insurance, prescription
- Fields containing: condition, diagnosis, treatment

### Authentication
- Fields containing: password, pwd, secret, token, key
- Fields containing: auth, credential, session

### Device/Network
- Fields containing: ip, mac, device, browser
- Fields containing: location, latitude, longitude, geo