import uvicorn

from tvp import config

if __name__ == "__main__":
    uvicorn.run(
        app="tvp.main:app",
        host=config.listen_ip,
        port=config.listen_port,
        reload=config.debug_mode,
    )
