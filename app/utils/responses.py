from fastapi.responses import JSONResponse

def success_response(data, message="success", status_code=200):
    return JSONResponse(content={"status": "success", "message": message, "data": data}, status_code=status_code)

def error_response(message="error", status_code=400):
    return JSONResponse(content={"status": "error", "message": message}, status_code=status_code)
