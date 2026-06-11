# Swarm test-app: nginx + Python

Minimale test-stack voor een 2-node Docker Swarm (swarm-manager + swarm-worker).
Twee stock images, géén eigen image en dus géén registry nodig: de Python-app
(één bestand, alleen stdlib) wordt als Docker **config** naar alle nodes
gedistribueerd.

```
browser/curl ──> web (nginx, poort 8080) ──> app (python, 4 replicas, verdeeld over beide nodes)
```

Elke app-replica antwoordt met zijn eigen container-hostname, zodat je de
load-balancing van Swarm direct ziet.

## 1. Bestanden naar de manager

```
multipass transfer app.py nginx.conf stack.yml swarm-manager:
```

Alleen de manager heeft de bestanden nodig — Swarm distribueert de configs,
en de stock images haalt elke node zelf van Docker Hub.

## 2. Swarm opzetten

IP van de manager opzoeken:

```
multipass list
```

Op de manager (`multipass shell swarm-manager`):

```
docker swarm init --advertise-addr <manager-IP>
```

Het `docker swarm join`-commando uit de output uitvoeren op de worker
(`multipass shell swarm-worker`). Controle op de manager:

```
docker node ls        # beide nodes Ready
```

## 3. Stack deployen

Op de manager:

```
docker stack deploy -c stack.yml demo
docker service ls                  # demo_app 4/4, demo_web 1/1
docker service ps demo_app         # replicas verdeeld over manager + worker
```

## 4. Testen

Vanaf de host-laptop (IP's uit `multipass list`):

```
curl http://<manager-IP>:8080      # paar keer herhalen
```

Elke request geeft een andere hostname terug → Swarm load-balanced over de
replicas. Ook `http://<worker-IP>:8080` werkt, óók als nginx daar niet draait:
dat is de **routing mesh**.

## 5. Schalen

```
docker service scale demo_app=8
docker service scale demo_app=2
```

Met `docker service ps demo_app` zie je de verdeling over de nodes veranderen.

## Opruimen

```
docker stack rm demo
```

## Resource-limits

In `stack.yml` staan per app-container limits (`cpus: 0.5`, `memory: 64M`) —
pas ze aan en deploy opnieuw (`docker stack deploy -c stack.yml demo` is
idempotent) om het effect te zien.

## Waarom geen eigen Dockerfile?

`docker stack deploy` negeert `build:` — Swarm bouwt geen images en kopieert
ze ook niet naar andere nodes. Een eigen image vereist dus een registry
(Docker Hub of self-hosted). Voor deze test is dat omzeild door stock images
te gebruiken en de app-code als Swarm-config te verspreiden.
