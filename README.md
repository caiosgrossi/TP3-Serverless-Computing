# TP3 Serverless Computing

Guia rápido para subir o runtime (worker) e o dashboard, localmente via Docker e em Kubernetes.

## Imagens Docker (build)
- Runtime: `docker build -t caiosgrossi/dashboard:runtime ./runtime`
- Dashboard: `docker build -t caiosgrossi/dashboard:v1 ./dashboard`

## Executar localmente
### Runtime
1) Prepare o código do usuário em `usermodule.py` (deve expor `handler(input, context)`).
2) Ajuste `runtime/.env` (defina `REDIS_OUTPUT_KEY`).
3) Rode o contêiner montando o arquivo: 
```
docker run --env-file .env -v /home/caiogrossi/TP3-Serverless-Computing/usermodule/mymodule.py:/opt/usermodule.py:ro caiosgrossi/dashboard:runtime
```

### Dashboard
Use suas variáveis de Redis (ajuste `REDIS_KEY`, `REDIS_HOST`, `REDIS_PORT`, `REFRESH_MS`):
```
docker run -p 50105:50105 --env-file .env caiosgrossi/dashboard:v1
```
Abra http://localhost:50105.

## Kubernetes
1) Crie ConfigMap com o código do usuário montado em `/opt/usermodule.py`:
```
kubectl create configmap pyfile --from-file=pyfile=usermodule/mymodule.py
```
2) Crie ConfigMap com a chave de saída do Redis:
```
kubectl create configmap outputkey --from-literal=REDIS_OUTPUT_KEY=<sua-output-key>
```
3) Ajuste hosts/ports/chaves nos manifests em `k8s/runtime-deployment.yaml` e `k8s/dashboard-deployment.yaml`.
4) Aplique:
```
kubectl apply -f k8s/runtime-deployment.yaml
kubectl apply -f k8s/dashboard-deployment.yaml
kubectl apply -f k8s/dashboard-service.yaml
```
5) Acesse o dashboard via o NodePort configurado (50105).