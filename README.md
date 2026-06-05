# Medical Integration Scaffold

This scaffold contains an integrated deployment of:

- `cios_v6` — Clinical Intelligence Operating System
- `ICU` — ICU Monitoring System

Both projects are copied into this folder so the stack can run independently from the original workspace.

## Layout

- `cios_v6/` — copy of the CIOS v6 application
- `ICU/` — copy of the ICU monitoring system
- `docker-compose.yml` — integrated stack

## Run the stack

```powershell
cd c:\PROJECTS\medical
./start_medical.ps1
```

Or on Windows you can run:

```cmd
cd c:\PROJECTS\medical
start_medical.bat
```

This will build and start the stack, then automatically open the CIOS frontend in your browser.

The services will be available on:

- CIOS backend: `http://localhost:8000`
- CIOS frontend: `http://localhost:3000`
- CIOS nginx gateway: `http://localhost:8080`
- ICU backend: `http://localhost:8001`
- ICU frontend: `http://localhost:5174`

## What is included

- CIOS backend, frontend, nginx, Postgres, Redis
- ICU backend, frontend, simulator, Postgres
- CIOS is configured to use the ICU monitoring DB through `ICU_DATABASE_URL`
- The `cios_v6` frontend is configured to open the ICU app at `http://localhost:5174`

## Notes

- The CIOS integration uses `ics_backend` and `icu_backend` containers for interoperability.
- If you need to reset data, stop the stack and remove the named volumes:

```bash
docker-compose down -v
```

- If you want to edit or extend the stack, use the `medical/docker-compose.yml` file.
