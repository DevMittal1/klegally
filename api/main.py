import uvicorn
from api.config import api_settings

if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host=api_settings.HOST,
        port=api_settings.PORT,
        reload=api_settings.DEBUG,
    )
