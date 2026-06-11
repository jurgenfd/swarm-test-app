# Swarm test-app: nginx + Python

Minimale test-stack voor een 2-node Docker Swarm (swarm-manager + swarm-worker).
Twee stock images, géén eigen image en dus géén registry nodig: de Python-app
(één bestand, alleen stdlib) wordt als Docker **config** naar alle nodes
gedistribueerd.

```
browser/curl ──> web (nginx, poort 8080) ──> app (python, 4 replicas, verdeeld over beide nodes)
```

Zie [architecture.puml](architecture.puml) voor het volledige architectuurdiagram.

Elke app-replica antwoordt met zijn eigen container-hostname, zodat je de
load-balancing van Swarm direct ziet.

> Getest op macOS (Apple Silicon, Multipass 1.16.3, Ubuntu 26.04 LTS,
> Docker 29.5.3) op 11-06-2026. Ook getest op Windows 10 Education
> (Hyper-V, Multipass 1.16.3, Ubuntu 24.04 LTS, Docker 29.5.3) op
> 11-06-2026 — alle stappen inclusief curl-tests vanaf de host werken
> ongewijzigd.

## 0. Host-setup (eenmalig): Multipass installeren

### macOS

```
brew install --cask multipass
```

De installer vraagt via `sudo` om je wachtwoord — voer dit commando dus zelf
in een terminal uit. Op een managed Mac heb je tijdelijke admin-rechten nodig
(bijv. via de Privileges-app) als je account geen admin is. Multipass gebruikt
het ingebouwde Virtualization-framework van Apple; MDM-beleid zit hierbij
normaal gesproken niet in de weg.

Controle:

```
multipass version
```

### Windows

Download de installer van <https://canonical.com/multipass/install> en let op
de hypervisor:

- **Windows 10/11 Pro/Enterprise/Education**: Multipass gebruikt Hyper-V (aanzetten via
  "Windows-onderdelen in- of uitschakelen" als dat nog niet aanstaat). VM-IP's
  zijn direct bereikbaar vanaf de host — de curl-tests hieronder werken dan
  ongewijzigd.
- **Windows Home**: geen Hyper-V; Multipass valt terug op VirtualBox. De
  VM-netwerken zijn dan standaard NAT, waardoor de VM-IP's uit
  `multipass list` mogelijk **niet** direct bereikbaar zijn vanaf de host.
  De stappen *binnen* de VM's (swarm init/join, deploy, schalen) werken
  identiek; voor de curl-test vanaf de host is extra netwerkconfiguratie
  nodig (port forwarding of een host-only adapter), of test je met curl
  vanuit een van de VM's zelf.

Alle commando's hieronder zijn verder identiek op macOS en Windows
(Terminal/PowerShell maakt geen verschil).

## 1. VM's aanmaken en Docker installeren

Twee Ubuntu-VM's aanmaken (2 CPU / 2 GB is ruim voldoende voor dit lab):

```
multipass launch --name swarm-manager --cpus 2 --memory 2G --disk 8G
multipass launch --name swarm-worker  --cpus 2 --memory 2G --disk 8G
```

De eerste launch downloadt het Ubuntu-image en duurt een paar minuten.
Daarna Docker in beide VM's installeren:

```
multipass exec swarm-manager -- bash -c "curl -fsSL https://get.docker.com | sudo sh"
multipass exec swarm-worker  -- bash -c "curl -fsSL https://get.docker.com | sudo sh"
```

De `ubuntu`-gebruiker in de VM's zit niet in de docker-groep: gebruik in de
VM's `sudo docker …`, of voer eenmalig
`multipass exec <vm> -- sudo usermod -aG docker ubuntu` uit (daarna opnieuw
inloggen).

## 2. Bestanden naar de manager

```
multipass transfer app.py nginx.conf stack.yml swarm-manager:
```

Alleen de manager heeft de bestanden nodig — Swarm distribueert de configs,
en de stock images haalt elke node zelf van Docker Hub.

## 3. Swarm opzetten

IP van de manager opzoeken:

```
multipass list
```

Op de manager (`multipass shell swarm-manager`):

```
sudo docker swarm init --advertise-addr <manager-IP>
```

Het `docker swarm join`-commando uit de output uitvoeren op de worker
(`multipass shell swarm-worker`). Controle op de manager:

```
sudo docker node ls        # beide nodes Ready
```

## 4. Stack deployen

Op de manager:

```
sudo docker stack deploy -c stack.yml demo
sudo docker service ls                  # demo_app 4/4, demo_web 1/1
sudo docker service ps demo_app         # replicas verdeeld over manager + worker
```

## 5. Testen

Vanaf de host-laptop (IP's uit `multipass list`):

```
curl http://<manager-IP>:8080      # paar keer herhalen
```

Elke request geeft een andere hostname terug → Swarm load-balanced over de
replicas. Ook `http://<worker-IP>:8080` werkt, óók als nginx daar niet draait:
dat is de **routing mesh**. (Windows Home/VirtualBox: zie de noot bij de
host-setup als de VM-IP's niet bereikbaar zijn.)

## 6. Schalen

```
sudo docker service scale demo_app=8
sudo docker service scale demo_app=2
```

Met `sudo docker service ps demo_app` zie je de verdeling over de nodes
veranderen. Opnieuw `sudo docker stack deploy -c stack.yml demo` zet het
aantal terug op de 4 uit `stack.yml`.

## Opruimen

Op de manager:

```
sudo docker stack rm demo
```

VM's stoppen (of helemaal weggooien) vanaf de host:

```
multipass stop swarm-manager swarm-worker
multipass delete --purge swarm-manager swarm-worker   # definitief verwijderen
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

## Bekende valkuil bij scripten

`multipass exec` blijft hangen (99% CPU) wanneer stdin `/dev/null` is, zoals
in achtergrond-shells of CI-stappen zonder stdin. Het commando ín de VM draait
gewoon door; alleen de multipass-wrapper hangt. Voer `multipass exec` daarom
altijd in de voorgrond uit.
