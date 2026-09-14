# Seller portal auth testing
The MVP uses a simulated phone OTP flow. Request an OTP at `/api/auth/request-otp` and verify with `123456` at `/api/auth/verify-otp`. No SMS provider is connected.