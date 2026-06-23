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

## Geteste platformen

Alle vier de platformen zijn getest met Multipass 1.16.3, Ubuntu 26.04 LTS
en Docker 29.5.3/29.6.0. Alle stappen, inclusief de curl-tests vanaf de host
(load-balancing én routing mesh), werken ongewijzigd.

### macOS - Apple Silicon (getest 11-06-2026).

### Windows 10 Education - Hyper-V (getest 11-06-2026).

### Windows 11 Pro - Hyper-V (getest 11-06-2026).

### Windows 11 Home - VirtualBox (getest 23-06-2026).

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

### Windows 10/11 Pro/Enterprise/Education

Download de installer van <https://canonical.com/multipass/install>.
Multipass gebruikt Hyper-V: zet dit aan via "Windows-onderdelen in- of
uitschakelen" als het nog niet aanstaat, daarna is een **herstart** vereist —
zonder herstart bestaat de Hyper-V-service nog niet en faalt `multipass launch`
met "The Hyper-V service does not exist". VM-IP's zijn direct bereikbaar vanaf
de host; alle commando's hieronder werken ongewijzigd.

### Windows Home

> **Tip voor studenten:** via **Azure Dev Tools for Teaching** (voorheen Azure
> Education / Azure for Students) kun je Windows 11 Education (N) gratis
> downloaden en als upgrade installeren. Education heeft wél Hyper-V, waardoor
> je de eenvoudigere Hyper-V-instructies hierboven kunt volgen. Kijk op
> <https://azureforeducation.microsoft.com/devtools> of je instelling
> deelneemt.

Windows Home heeft geen Hyper-V. Multipass gebruikt dan VirtualBox, dat je
**apart moet installeren** vóór je Multipass installeert:

```
winget install Oracle.VirtualBox
winget install Canonical.Multipass
```

Of download beide installers handmatig:
- VirtualBox: <https://www.virtualbox.org/wiki/Downloads>
- Multipass: <https://canonical.com/multipass/install>

Open na de installatie een **nieuw** terminalvenster zodat `multipass` in het
PATH staat.

**Eerste start kan time-outen.** Bij de allereerste `multipass launch` kan de
VM een time-out geven terwijl de VirtualBox-kernel-driver zich initialiseert.
De foutmelding eindigt op `launch failed: Could not start VM: Process operation
timed out`. Herstel:

```
# PowerShell (als administrator)
Restart-Service Multipass
```

Probeer `multipass launch` daarna opnieuw; de tweede poging slaagt wel.

**Netwerk: gebruik `--network` bij aanmaken van de VM's.** Zonder extra vlag
krijgen beide VM's hetzelfde NAT-adres (`10.0.2.15`) en kunnen ze elkaar niet
bereiken. Voeg de WiFi- of Ethernet-adapter van de host toe als bridged
interface (zie stap 1 hieronder); dan krijgt elke VM een eigen IP op je
lokale netwerk en werken ook de curl-tests vanaf de host ongewijzigd.

Controleer welke adapternamen beschikbaar zijn:

```
multipass networks
```

Typische uitvoer: `WiFi` en `Ethernet`. Gebruik de naam die actief is op jouw
host (zie stap 1).

Alle overige commando's zijn identiek op macOS en Windows
(Terminal/PowerShell maakt geen verschil).

## 1. VM's aanmaken en Docker installeren

Twee Ubuntu-VM's aanmaken (2 CPU / 2 GB is ruim voldoende voor dit lab):

**macOS en Windows (Hyper-V):**

```
multipass launch --name swarm-manager --cpus 2 --memory 2G --disk 8G
multipass launch --name swarm-worker  --cpus 2 --memory 2G --disk 8G
```

**Windows Home (VirtualBox):** voeg `--network <adapter>` toe zodat elke VM
een eigen IP krijgt op je lokale netwerk. Vervang `WiFi` door `Ethernet` als
de host via kabel verbonden is:

```
multipass launch --name swarm-manager --cpus 2 --memory 2G --disk 8G --network WiFi
multipass launch --name swarm-worker  --cpus 2 --memory 2G --disk 8G --network WiFi
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

**Windows Home:** `multipass list` toont `172.17.0.1` (de Docker bridge) in
plaats van het echte VM-adres. Gebruik dit commando om alle interfaces te zien:

```
multipass exec swarm-manager -- hostname -I
```

De uitvoer bevat meerdere IP's (`10.0.2.15` is NAT, `172.17.0.1` is Docker).
Gebruik het adres in het bereik van je thuisnetwerk, bijv. `192.168.x.x`.

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
dat is de **routing mesh**. Bij Windows Home werkt dit alleen als de VM's
aangemaakt zijn met `--network` (zie stap 1); zonder die vlag zijn de
VM-IP's niet bereikbaar vanaf de host.

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
