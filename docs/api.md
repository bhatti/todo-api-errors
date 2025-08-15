# Protocol Documentation
<a name="top"></a>

## Table of Contents

- [api/proto/errors/v1/errors.proto](#api_proto_errors_v1_errors-proto)
    - [ErrorDetail](#errors-v1-ErrorDetail)
    - [ErrorDetail.ExtensionsEntry](#errors-v1-ErrorDetail-ExtensionsEntry)
    - [FieldViolation](#errors-v1-FieldViolation)
  
    - [AppErrorCode](#errors-v1-AppErrorCode)
  
- [Scalar Value Types](#scalar-value-types)



<a name="api_proto_errors_v1_errors-proto"></a>
<p align="right"><a href="#top">Top</a></p>

## api/proto/errors/v1/errors.proto



<a name="errors-v1-ErrorDetail"></a>

### ErrorDetail
ErrorDetail provides a structured, machine-readable error payload.
It is designed to be embedded in the `details` field of a `google.rpc.Status` message.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| code | [string](#string) |  | A unique, application-specific error code. |
| title | [string](#string) |  | A short, human-readable summary of the problem type. |
| detail | [string](#string) |  | A human-readable explanation specific to this occurrence of the problem. |
| field_violations | [FieldViolation](#errors-v1-FieldViolation) | repeated | A list of validation errors, useful for INVALID_ARGUMENT responses. |
| trace_id | [string](#string) |  | Optional trace ID for request correlation |
| timestamp | [google.protobuf.Timestamp](#google-protobuf-Timestamp) |  | Optional timestamp when the error occurred |
| instance | [string](#string) |  | Optional instance path where the error occurred |
| extensions | [ErrorDetail.ExtensionsEntry](#errors-v1-ErrorDetail-ExtensionsEntry) | repeated | Optional extensions for additional error context |






<a name="errors-v1-ErrorDetail-ExtensionsEntry"></a>

### ErrorDetail.ExtensionsEntry



| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| key | [string](#string) |  |  |
| value | [google.protobuf.Any](#google-protobuf-Any) |  |  |






<a name="errors-v1-FieldViolation"></a>

### FieldViolation
Describes a single validation failure.


| Field | Type | Label | Description |
| ----- | ---- | ----- | ----------- |
| field | [string](#string) |  | The path to the field that failed validation, e.g., &#34;title&#34;. |
| description | [string](#string) |  | A developer-facing description of the validation rule that failed. |
| code | [string](#string) |  | Application-specific error code for this validation failure |





 


<a name="errors-v1-AppErrorCode"></a>

### AppErrorCode
AppErrorCode defines a list of standardized, application-specific error codes.

| Name | Number | Description |
| ---- | ------ | ----------- |
| APP_ERROR_CODE_UNSPECIFIED | 0 |  |
| VALIDATION_FAILED | 1 | Validation failures |
| REQUIRED_FIELD | 2 |  |
| TOO_SHORT | 3 |  |
| TOO_LONG | 4 |  |
| INVALID_FORMAT | 5 |  |
| MUST_BE_FUTURE | 6 |  |
| INVALID_VALUE | 7 |  |
| DUPLICATE_TAG | 8 |  |
| INVALID_TAG_FORMAT | 9 |  |
| OVERDUE_COMPLETION | 10 |  |
| EMPTY_BATCH | 11 |  |
| BATCH_TOO_LARGE | 12 |  |
| DUPLICATE_TITLE | 13 |  |
| RESOURCE_NOT_FOUND | 1001 | Resource errors |
| RESOURCE_CONFLICT | 1002 |  |
| AUTHENTICATION_FAILED | 2001 | Authentication and authorization |
| PERMISSION_DENIED | 2002 |  |
| RATE_LIMIT_EXCEEDED | 3001 | Rate limiting and service availability |
| SERVICE_UNAVAILABLE | 3002 |  |
| INTERNAL_ERROR | 9001 | Internal errors |


 

 

 



## Scalar Value Types

| .proto Type | Notes | C++ | Java | Python | Go | C# | PHP | Ruby |
| ----------- | ----- | --- | ---- | ------ | -- | -- | --- | ---- |
| <a name="double" /> double |  | double | double | float | float64 | double | float | Float |
| <a name="float" /> float |  | float | float | float | float32 | float | float | Float |
| <a name="int32" /> int32 | Uses variable-length encoding. Inefficient for encoding negative numbers – if your field is likely to have negative values, use sint32 instead. | int32 | int | int | int32 | int | integer | Bignum or Fixnum (as required) |
| <a name="int64" /> int64 | Uses variable-length encoding. Inefficient for encoding negative numbers – if your field is likely to have negative values, use sint64 instead. | int64 | long | int/long | int64 | long | integer/string | Bignum |
| <a name="uint32" /> uint32 | Uses variable-length encoding. | uint32 | int | int/long | uint32 | uint | integer | Bignum or Fixnum (as required) |
| <a name="uint64" /> uint64 | Uses variable-length encoding. | uint64 | long | int/long | uint64 | ulong | integer/string | Bignum or Fixnum (as required) |
| <a name="sint32" /> sint32 | Uses variable-length encoding. Signed int value. These more efficiently encode negative numbers than regular int32s. | int32 | int | int | int32 | int | integer | Bignum or Fixnum (as required) |
| <a name="sint64" /> sint64 | Uses variable-length encoding. Signed int value. These more efficiently encode negative numbers than regular int64s. | int64 | long | int/long | int64 | long | integer/string | Bignum |
| <a name="fixed32" /> fixed32 | Always four bytes. More efficient than uint32 if values are often greater than 2^28. | uint32 | int | int | uint32 | uint | integer | Bignum or Fixnum (as required) |
| <a name="fixed64" /> fixed64 | Always eight bytes. More efficient than uint64 if values are often greater than 2^56. | uint64 | long | int/long | uint64 | ulong | integer/string | Bignum |
| <a name="sfixed32" /> sfixed32 | Always four bytes. | int32 | int | int | int32 | int | integer | Bignum or Fixnum (as required) |
| <a name="sfixed64" /> sfixed64 | Always eight bytes. | int64 | long | int/long | int64 | long | integer/string | Bignum |
| <a name="bool" /> bool |  | bool | boolean | boolean | bool | bool | boolean | TrueClass/FalseClass |
| <a name="string" /> string | A string must always contain UTF-8 encoded or 7-bit ASCII text. | string | String | str/unicode | string | string | string | String (UTF-8) |
| <a name="bytes" /> bytes | May contain any arbitrary sequence of bytes. | string | ByteString | str | []byte | ByteString | string | String (ASCII-8BIT) |

