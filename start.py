import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    
    # Usar múltiples workers para producción. 
    # Por defecto 4, pero puedes moverlo a una variable de entorno si quieres.
    workers = int(os.environ.get("WEB_CONCURRENCY", 4))

    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        loop="uvloop",      # Optimización de evento loop (incluida en uvicorn[standard])
        http="httptools",   # Parser HTTP ultra rápido (incluido en uvicorn[standard])
        log_level="info"
    )