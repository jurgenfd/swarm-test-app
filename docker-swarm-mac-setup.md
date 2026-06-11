# Docker Swarm lab — setup op Apple Silicon Mac

Werkdocument voor het opzetten van een lokale 2-node Docker Swarm omgeving voor het derdejaars HBO-blok Containers. Doel: studenten meerdere containers laten draaien met variabele resources, gratis en zonder creditcard.

## Context en keuzes

### Online platforms onderzocht (mei 2026)

| Platform | Status | Geschikt? |
|---|---|---|
| Play with Docker | **Stopgezet 1 maart 2026** | Nee |
| Play with Kubernetes | **Stopgezet 1 maart 2026** | Nee |
| dockerlabs.xyz | Offline | Nee |
| Killercoda | Werkt, eigen scenario's via Git-repo mogelijk | Ja, voor K8s |
| KodeKloud Public Playgrounds | Werkt, 1 node | Beperkt |
| iximiuz Labs | Werkt, multi-node via `kubeadm` | Ja, voor K8s |
| LabEx | Werkt | Ja, voor K8s |

**Conclusie:** voor multi-node **Swarm** is er geen goede gratis browser-vervanger meer sinds PWD weg is. Daarom: lokaal opzetten via VM-tooling.

### RAM-budget

Per VM met Docker + 2 lichte containers:
- Ubuntu Server minimal: ~1 GB
- Alpine Linux: ~512 MB

Host (laptop) totaal:
- Bare minimum (Alpine, niets anders open): 8 GB
- Aanbevolen voor handleiding: **16 GB**

### VM-tooling op Mac (gratis, zonder CC)

| Tool | Verdict |
|---|---|
| **Multipass + Ubuntu** | Eerste keuze; gefaald op M4 Pro / macOS 26.5 door QEMU SME-bug (zie [issue #3842](https://github.com/canonical/multipass/issues/3842)) |
| **Lima + Ubuntu** | **Werkt**; gebruikt Apple Virtualization.framework (VZ), omzeilt QEMU-bug |
| Lima + Alpine | Werkt in principe, maar cloud-init traag op eerste boot |
| UTM | GUI-alternatief, meer handwerk |

## Actuele setup: Lima + Ubuntu 24.04

### Installatie

```
brew install lima
```

### Twee VMs aanmaken

```
limactl start --name=swarm-manager --cpus=1 --memory=1 template:ubuntu-lts
limactl start --name=swarm-worker  --cpus=1 --memory=1 template:ubuntu-lts
```

Wachten tot `READY` — niet onderbreken. Tweede VM kan trager booten als er nog activiteit van de eerste is.

### Status verifiëren

```
limactl list
```
Beide moeten `Running` zijn met een eigen SSH-poort.

### Docker installeren (in elke VM)

```
limactl shell swarm-manager
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
```
En idem voor `swarm-worker`.

## Bevindingen tijdens setup (empirisch)

- **Multipass 1.16.2 is stuk op M4 Pro / macOS 26.5.** QEMU-fout `Property 'host-arm-cpu.sme' not found`. Geen workaround binnen Multipass; wachten op nieuwe release. Lima sidesteped dit doordat het VZ gebruikt i.p.v. QEMU.
- **Lima syntax-wijziging vanaf v2.0**: `template:ubuntu-lts` i.p.v. `template://ubuntu-lts`. Oude vorm geeft alleen een warning, werkt nog wel.
- **Alpine cloud-init op Lima is traag op eerste boot.** Met 512 MB RAM gaf het SSH-timeouts; met 1 GB werkt het, maar Ubuntu boot sneller en zonder gedoe → Ubuntu gekozen.
- **Boot-tijd is wisselvallig per VM.** Manager: 78 sec. Worker (gestart terwijl manager nog netwerk-forwarders opzette): >600 sec, Lima gaf `did not receive an event with the "running" status` maar VM kwam alsnog up. Les: VMs sequentieel starten en geduldig zijn.
- **IP-collisie tussen Lima VMs bevestigd**: beide swarm-manager en swarm-worker krijgen `192.168.5.15/24` op `eth0` (eigen usernet, zelfde IP). Onbruikbaar voor Swarm zonder extra netwerk.

### Schoonmaak-commando's die werken

Multipass volledig weg:
```
multipass delete --all
multipass purge
brew uninstall --cask multipass
sudo rm -rf /var/root/Library/Application\ Support/multipassd
rm -rf ~/Library/Application\ Support/multipass*
```

Lima volledig weg:
```
limactl list -q | xargs -r limactl delete --force
brew uninstall lima
rm -rf ~/.lima
```

## Huidige blokkade: Lima-netwerk

Standaard krijgen alle Lima VMs op Apple Silicon **hetzelfde usernet-IP `192.168.5.15`** — elk in een eigen NAT. Ze kunnen elkaar dus niet bereiken, wat Swarm onmogelijk maakt. Empirisch bevestigd op deze setup (zie bevindingen hierboven).

### Oplossing: vzNAT gedeeld netwerk

1. Beide VMs stoppen:
   ```
   limactl stop swarm-manager
   limactl stop swarm-worker
   ```

2. Per VM de config bewerken:
   ```
   limactl edit swarm-manager
   ```
   Sectie `networks:` toevoegen of aanvullen met:
   ```yaml
   networks:
     - vzNAT: true
   ```
   Hetzelfde voor `swarm-worker`.

3. Beide weer starten:
   ```
   limactl start swarm-manager
   limactl start swarm-worker
   ```

4. Nieuwe IPs checken (verwacht een tweede interface, bijv. `enp0s2`):
   ```
   limactl shell swarm-manager -- ip -4 addr show
   limactl shell swarm-worker  -- ip -4 addr show
   ```

5. Connectiviteit testen:
   ```
   limactl shell swarm-manager -- ping -c 3 <worker-IP>
   ```

## Volgende stappen (zodra netwerk werkt)

### Swarm initialiseren

Op de manager, met het IP van de gedeelde-netwerk-interface:
```
docker swarm init --advertise-addr <manager-IP>
```

Output bevat een `docker swarm join`-commando met token. Dat uitvoeren op de worker.

### Service met meerdere containers

```
docker service create --name web --replicas 4 \
  --limit-memory 64M --limit-cpu 0.5 \
  -p 8080:80 nginx:alpine
```

Met 4 replicas verdeelt Swarm ~2 containers per node. Resource-limits per container instelbaar via `--limit-memory` / `--limit-cpu`.

### Schalen

```
docker service scale web=8
docker service scale web=2
```

## Lifecycle: starten en stoppen na reboot

Lima VMs **starten niet automatisch** na een Mac-reboot of uitlog. Na een herstart staan beide VMs op `Stopped` — handmatig weer aanzetten:

```
limactl start swarm-manager swarm-worker
```

### Aanrader voor het lab: shell-alias

In `~/.zshrc` of `~/.bashrc`:
```
alias swarm-up='limactl start swarm-manager swarm-worker'
alias swarm-down='limactl stop swarm-manager swarm-worker'
```

Didactisch beter dan onzichtbare autostart — studenten zien expliciet de VM-lifecycle.

### Optioneel: autostart bij login via LaunchAgent

Bestand `~/Library/LaunchAgents/com.local.lima-swarm.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.local.lima-swarm</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/limactl</string>
    <string>start</string>
    <string>swarm-manager</string>
    <string>swarm-worker</string>
  </array>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
```

Activeren met `launchctl load ~/Library/LaunchAgents/com.local.lima-swarm.plist`.

Nadelen: vertraagt login 30–60s, en bij kapotte VM blokkeert hij stilletjes op de achtergrond. Voor een lab-omgeving overdreven.

### Containers na node-reboot

Lopende containers worden **niet automatisch hersteld** tenzij:
- Ze met `--restart=unless-stopped` of `--restart=always` zijn gestart, óf
- Ze in een Swarm service draaien — Swarm replanned services automatisch zodra de node terug is.

Zodra Swarm draait, regelt Swarm zelf de service-resilience. Geen extra autostart op container-niveau nodig.

## Voor in de studiehandleiding

- Eis: macOS met Apple Silicon (M1/M2/M3/M4), 16 GB RAM, virtualisatie aan.
- Tool: Lima (gratis, brew install).
- VMs: 2× Ubuntu 24.04, 1 GB RAM / 1 CPU elk.
- Netwerk: `vzNAT: true` in `limactl edit`.
- Alles als Infra-as-Code in Git bewaren — sessies kunnen verloren gaan, dan `git clone` + opnieuw applyen.

## Windows als host-OS — bekende issues

Windows is duidelijk de grilligste host voor dit lab. Belangrijkste struikelblokken:

### Windows-editie blokkeert tool-keuzes

- **Hyper-V** en **Multipass + Hyper-V backend**: alleen Pro / Enterprise / Education.
- **WSL2**: wel beschikbaar op Home, gebruikt Hyper-V-componenten onder de motorkap.
- Veel studenten hebben **Windows Home** → één uniforme instructie betekent kiezen voor de laagste gemene deler (VirtualBox).

### Hypervisor-conflicten

Eén hypervisor tegelijk mag de CPU-virtualisatie hebben:
- WSL2 + Docker Desktop ↔ VirtualBox bijten elkaar historisch.
- VirtualBox 7.x + Windows 11 via WHPX werkt, maar performance 2–5× trager.
- Hyper-V/WSL2 uitschakelen om VirtualBox snel te krijgen is onomkeerbaar voor wie WSL2 elders nodig heeft.

### Virtualisatie in BIOS staat vaak uit

Op goedkopere/oudere laptops (Acer, Lenovo Ideapad, sommige HP's) is VT-x / AMD-V default disabled. Reken op 1–2 studenten per klas die hier vastlopen, soms zonder BIOS-toegang vanwege secure boot/OEM-tooling.

### Docker Desktop licentie-issue

Voor het HBO als organisatie (>250 medewerkers) is Docker Desktop niet gratis. Persoonlijk studentgebruik mag nog wel, maar schoolbeleid kan blokkeren. **Met Multipass/Lima/Vagrant + `apt install docker.io` binnen de VM is Docker Desktop overbodig.**

### WSL2 geeft geen multi-node Swarm

WSL2 = één gedeelde Linux-VM. Meerdere distros draaien op dezelfde kernel. Voor twee échte Swarm-nodes is het niet bruikbaar. Workarounds (DinD, kind) zijn didactisch verwarrend.

### Architectuur-verschil ARM64 vs x86_64

Mac instructies gebruiken `arm64`, Windows `amd64`. Voor multi-arch images (nginx, redis, ubuntu, alpine) geen probleem. Zelfgebouwde images: expliciet `--platform linux/amd64` in handleiding.

### Antivirus / corporate beperkingen

Corporate AV (McAfee, Symantec, CrowdStrike) op stage- of bruikleenlaptops blokkeert soms VM-creatie of Hyper-V. Vaak zonder duidelijke foutmelding — lastig op afstand te diagnosticeren.

## Aanbevolen Windows-paden voor de handleiding

| Edition | Primair pad | Fallback |
|---|---|---|
| Windows 11 Pro / Edu / Enterprise | **Multipass + Hyper-V** (vrijwel identiek aan Mac-instructies) | Vagrant + VirtualBox |
| Windows 11 Home | **Vagrant + VirtualBox** met Vagrantfile uit Git | Killercoda online |
| Laptop weigert virtualisatie / corporate AV | Killercoda online (alleen K8s — Swarm vervalt) | — |

### Vagrantfile (schets)

Plaats in de root van de student-repo. Eén `vagrant up` zet beide VMs op met Docker geïnstalleerd en een privé-bridge waarover Swarm kan praten.

```ruby
Vagrant.configure("2") do |config|
  nodes = {
    "swarm-manager" => "192.168.56.10",
    "swarm-worker"  => "192.168.56.11"
  }

  nodes.each do |name, ip|
    config.vm.define name do |node|
      node.vm.box = "bento/ubuntu-24.04"
      node.vm.hostname = name
      node.vm.network "private_network", ip: ip
      node.vm.provider "virtualbox" do |vb|
        vb.memory = 1024
        vb.cpus   = 1
      end
      node.vm.provision "shell", inline: <<-SHELL
        curl -fsSL https://get.docker.com | sh
        usermod -aG docker vagrant
      SHELL
    end
  end
end
```

Daarna:
```
vagrant up
vagrant ssh swarm-manager
docker swarm init --advertise-addr 192.168.56.10
# token uit output kopiëren, dan:
vagrant ssh swarm-worker
docker swarm join --token <TOKEN> 192.168.56.10:2377
```

Voordeel ten opzichte van Lima/Multipass: **identiek op Windows en Linux**, en in theorie ook op Intel-Mac. Apple Silicon valt af (VirtualBox draait niet native op ARM64).

## Openstaande punten

- [ ] Verifiëren dat `vzNAT` op studenten-Macs zonder admin-rechten werkt.
- [ ] Vagrantfile testen op Windows Home + Pro, en op Intel-Mac.
- [ ] BIOS-check stap met screenshots voor 3 meest voorkomende laptopmerken in handleiding.
- [ ] Beslissen of Swarm-deel didactisch behouden blijft of vervangen door alleen Kubernetes.
- [ ] Killercoda-account vooraf laten aanmaken door alle studenten als safety net.
- [ ] Killercoda-scenario('s) schrijven als online-fallback.
