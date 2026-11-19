.PHONY: up down logs seed test clean sim-off sim-on ps pronostico

## Levanta el backend con simulador (no necesitas hardware).
## El frontend NO se levanta aca: corre nativo con "cd web && npm run dev".
up:
	docker compose --profile sim up -d --build
	@echo ""
	@echo "  API docs  : http://localhost:8001/docs"
	@echo "  MQTT      : localhost:1883"
	@echo "  Redis     : localhost:6380"
	@echo ""
	@echo "  Frontend:         cd web && npm run dev"
	@echo "  Datos de prueba:  make seed"

## Carga sedes y aulas de ejemplo
seed:
	docker compose exec api python -m app.seed

## Logs de todos los servicios
logs:
	docker compose logs -f api worker simulator

ps:
	docker compose ps

## Apaga el simulador (cuando ya tengas el ESP32 conectado)
sim-off:
	docker compose stop simulator

sim-on:
	docker compose --profile sim up -d simulator

test:
	docker compose exec api pytest -q

## Ensena al pronostico del aire con el historial (ver backend/aprendizaje/)
pronostico:
	docker compose exec api python -m aprendizaje.entrenar

down:
	docker compose down

## Borra tambien los volumenes (base de datos incluida)
clean:
	docker compose down -v
