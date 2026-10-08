# Hosting AgentForge step by step

This guide is for the first public deployment. Run Linux commands **on the VM**, not in Windows PowerShell. Local development continues to use `docker compose up`; production uses both Compose files and a separate `.env.production`.

## 1. Choose hosting and control spending

Recommended architecture: one dedicated Ubuntu 24.04 x86-64 VM, 2 vCPUs, 4 GB RAM, at least 40 GB disk, Docker Engine, and Caddy. The trusted gateway needs Docker daemon access, which makes a VM a practical fit. All application services remain private behind one HTTPS origin. Keep this host separate from personal workloads.

| Choice | Use it when | Decision |
|---|---|---|
| Azure VM using Azure for Students | You qualify as a full-time university student | First choice for available student credit |
| AWS Lightsail Linux VM with public IPv4, 4 GB RAM | You need a predictable paid fallback | Straightforward all-in-one VM setup |
| Existing suitable VM | You already own one | Prefer it to provisioning another resource |

As checked October 9, 2026, [Azure for Students](https://azure.microsoft.com/en-us/free/students/) advertises $100 credit usable within 12 months and no credit card requirement. Eligibility and subscription quotas apply. The required 4 GB VM is **not assumed to be included in free monthly VM allowances**. Review compute, disk, public-IP and bandwidth charges in the portal.

[Lightsail pricing](https://aws.amazon.com/lightsail/pricing/) lists the 4 GB Linux/public-IPv4 bundle at $24/month; domain, backup, overage, and tax can add costs. Check the final quote before creation. Neither credit availability nor perpetual free hosting is promised.

Use a budget alert and review it regularly. [Azure budgets](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets) are alerts, not an automatic spending cap. Keep student spending protection unless you intentionally accept pay-as-you-go charges. Model-provider charges are separate; start with the `demo` planner and leave model keys blank.

## 2. Create the VM

For Azure, follow the [official portal VM guide](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/quick-create-portal), applying these project choices:

1. Select your student subscription and create a dedicated resource group `agentforge-demo`.
2. Select Ubuntu Server **24.04 LTS**, x86-64, a region near you, and a VM size with **2 vCPUs / 4 GB RAM**. Choose an available size and inspect its estimate; do not accept a larger default silently.
3. Use an SSH public key and username `azureuser`. Store the private key only on your computer, outside the repository. Do not paste it into chat or commit it.
4. Use a Standard static public IPv4 address. See [Azure public-IP setup](https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/create-public-ip-portal).
5. Configure cloud network rules: TCP 22 from your own public IP only; TCP 80/443 from the Internet. Keep 8000/8080/5432/6379/8001 closed. Apply the policy to IPv6 too if enabled.
6. Review the complete estimate before selecting Create. Account enrollment, identity verification, and paid resource creation are operator steps.

For Lightsail, choose Linux/Unix → Ubuntu 24.04, public IPv4, 4 GB bundle. Attach a static IP, restrict SSH to your IP, and allow 80/443. The remaining Linux procedure is the same; the SSH username is normally `ubuntu`.

If SSH access stops after your home IP changes, update only its cloud firewall source rule. Do not temporarily open SSH to everyone.

## 3. Connect and point DNS to the VM

On your Windows computer, connect with your actual key and IP:

```powershell
ssh -i "$env:USERPROFILE\.ssh\agentforge.pem" azureuser@VM_PUBLIC_IP
```

Verify the first connection's host-key fingerprint through the cloud console before accepting it. Do not disable host-key checking.

Choose a domain/subdomain you control, such as `forge.yourdomain.com`. Create an **A record** pointing to the static IPv4 address. Add an AAAA record only if IPv6 routing/firewall are correctly configured; stale AAAA records can break certificate issuance. Initially use direct DNS rather than adding another proxy layer.

On your computer, check propagation:

```powershell
Resolve-DnsName forge.yourdomain.com -Type A
```

The returned address must match the VM. [Caddy HTTPS requirements](https://caddyserver.com/docs/quick-starts/https) include correct DNS and reachable 80/443. A registrar-supplied subdomain you control is sufficient; a new paid domain is optional if you already have one.

## 4. Install Docker and basic tools on the VM

Use [Docker's official Ubuntu apt instructions](https://docs.docker.com/engine/install/ubuntu/), not an unreviewed convenience script. On a fresh Ubuntu 24.04 host:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git python3 python3-venv
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<'EOF'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
sudo docker compose version
```

Compose must be at least **2.24.4** for `!reset`. Docker-published ports can bypass UFW rules; rely on the cloud firewall as well as explicit Compose port publishing. Do not expose Docker TCP ports 2375/2376. This guide uses `sudo docker` rather than granting Docker group membership, which is effectively privileged access.

## 5. Prepare a separate production environment

On the VM:

```bash
git clone https://github.com/artignite3/agentforge.git
cd agentforge
python3 scripts/prepare_deploy.py --domain forge.yourdomain.com
chmod 600 .env.production
sudo python3 scripts/deploy_check.py --require-engine
```

Replace the hostname with your real domain. Preparation rejects URLs, IPs, wildcards, reserved names, and configuration syntax. It creates fresh API/gateway/database credentials, sets production mode, and detects the Docker socket group. It refuses to overwrite an existing file and leaves development `.env` untouched.

Keep `.env.production` only on the target host and in an encrypted recovery store. Add model keys privately if wanted, then review model IDs/rates and provider-side spending caps. Same-origin `/api` means browser CORS stays `[]`; the override enforces this even if development variables remain in your shell.

The checks inspect **resolved** Compose configuration without printing its secrets. Avoid running plain `docker compose config` into shared logs because it expands credentials.

## 6. Build, migrate, and start

Define a helper for this shell session; rerun its definition after reconnecting:

```bash
dc() { sudo docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.production.yml "$@"; }
dc build
dc run --rm migrate
dc up -d --wait --wait-timeout 180
dc ps
```

Only the edge publishes 80/443. The API and frontend's development host ports are removed, rather than appended to production ports. Caddy runs as UID/GID 10001 on internal high ports; named volumes persist its certificate/account data. Its admin API and access logging are disabled. Application data APIs retain bearer authentication.

The edge base image is pinned to the digest validated during this release. Review scans and deliberately update that digest as patches are released. Other existing stack images still use version tags; scan and pin the chosen release images before public-host signoff.

`--wait` verifies available container health checks; it does **not** prove public DNS/TLS or worker progress. Caddy's certificate issuance may take additional time. Inspect `dc logs --tail 50 edge` for issuance errors; do not repeatedly restart it and trigger CA limits. Investigate DNS, firewall, or another service occupying 80/443 first.

## 7. Verify the actual public release

Install the small client environment on the VM:

```bash
python3 -m venv .release-venv
.release-venv/bin/pip install .
.release-venv/bin/python scripts/verify_release.py --url https://forge.yourdomain.com --run-demo
```

This verifies frontend/API readiness, HSTS, unauthorized rejection, authenticated production mode, sandbox readiness, and a complete regression repair. It validates normal TLS certificates and does not follow redirects carrying credentials.

Also load the URL from your laptop or a mobile connection outside the cloud network. Select Connect workspace and enter the host's `AGENTFORGE_API_KEY` privately. Do not publish the key in a README. The public landing/dashboard can be shared without the key; viewing execution data or submitting jobs needs authorization.

Verify the original failed tests, patch, passing tests, and completed trace. Before declaring release, verify worker crash recovery/cancellation and UID/resource/network restrictions on this host using the existing tests and release checklist. A local test pass does not establish a hardened public execution environment.

## 8. Back up and restore before relying on persistence

```bash
mkdir -p backups
sudo python3 scripts/backup.py --output backups/pre-release.dump
```

The helper invokes Docker through the current user's permissions. In this sudo-based setup the archive is root-owned with mode 600. It writes binary bytes safely, refuses overwrite, and verifies `pg_restore --list`. Encrypt it and copy it off-host using appropriately authorized access. That validation is not a restoration drill.

Restore to a **new empty database**, never over the running database:

```bash
dc exec -T postgres createdb -U agentforge agentforge_restore_check
sudo cat backups/pre-release.dump | dc exec -T postgres pg_restore -U agentforge -d agentforge_restore_check --exit-on-error
dc exec -T postgres psql -U agentforge -d agentforge_restore_check -c 'SELECT count(*) FROM runs;'
```

If the scratch database already exists, choose another name. Review table counts and migration version against the source. Never pass `--clean` against production for a rehearsal. Retain or remove only the identified scratch database after review. Choose backup frequency/RPO/RTO before operating the service; this package does not schedule backups automatically.

## 9. Updates, rollback, and shutdown

Before updates: create a new uniquely named backup, save the current Git SHA, review migration compatibility, and test on a separate environment. For controlled upgrades, stop `worker` and `api`, update/build the reviewed revision, apply migrations, then restart and rerun release verification. This baseline has a maintenance window rather than zero-downtime releases.

Reverting code is safe only when that revision supports the current schema. For incompatible migrations, restore a verified backup into a new database/volume with the compatible code and switch deliberately. Do not attempt automatic Alembic downgrades or `down -v`.

`dc stop` preserves data; named PostgreSQL/Caddy volumes are needed for recovery. Cloud resource stopping/deallocation does not guarantee that disks, IPs, snapshots, or other retained resources stop billing. Inspect the provider bill and preserve backups before eventual resource deletion.

## Release boundary

Prepared and testable: Compose isolation, TLS configuration, environment generation, preflight, release smoke, backups, and CI. Operator prerequisites: account eligibility/budget, VM, SSH access, DNS. Actual public-host TLS, restoration, image vulnerability scans, recovery and isolation checks remain required.

The gateway's Docker socket is a privileged trust boundary and containers share a kernel. Use this for an operator-controlled portfolio demo, not arbitrary hostile multi-tenant jobs. No Kubernetes, managed database, or load balancer is necessary for this first release.
