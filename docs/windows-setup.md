# Set up Habitat on Windows

Use a dedicated Ubuntu 24.04 WSL2 distribution. Keep it separate from Linux
environments that need Windows drive access or Windows executable integration.
The commands below are setup instructions for your machine. Cloning this
repository does not install or reconfigure WSL.

## Prepare Linux

1. Follow Microsoft's [WSL installation instructions](https://learn.microsoft.com/en-us/windows/wsl/install).
   In PowerShell, inspect the available and installed distributions:

   ```powershell
   wsl --list --online
   wsl --list --verbose
   ```

2. If `Ubuntu-24.04` is not already installed, install it:

   ```powershell
   wsl --install --distribution Ubuntu-24.04
   ```

   Create your Linux user when prompted. If you already use that distribution,
   use Microsoft's [distribution import procedure](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro)
   to create a separate instance with a distinct name. Use that actual name in
   later commands. Do not overwrite an existing distribution.

3. Inside the dedicated distribution, install Docker Engine and its Compose
   plugin using [Docker's Ubuntu apt repository instructions](https://docs.docker.com/engine/install/ubuntu/).
   Use the documented specific-version installation path and record the versions
   you select. The original sandbox used Docker Engine 29.7.2. This export does
   not install Docker Desktop or change an existing Docker installation.

4. Configure your Linux user's Docker access using
   [Docker's post-installation instructions](https://docs.docker.com/engine/install/linux-postinstall/).
   Docker access gives that user control over the Linux distribution. Keep
   unrelated personal files and credentials out of this distribution.

5. Verify the tools inside Linux:

   ```bash
   uname -m
   id -u
   docker version
   docker compose version
   ```

   This export targets `x86_64` with a project directory writable by UID 1000.
   It has not been validated for ARM hosts or a different project owner UID.

## Isolate the dedicated distribution

Inside Linux, merge [the example WSL settings](../examples/wsl.conf) into
`/etc/wsl.conf` using an editor with `sudo`. Preserve your existing `[user]`
section. These settings enable systemd and disable Windows drive automount and
Windows executable integration. Microsoft documents their scope in
[advanced WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config).

Save your work and exit Linux. In PowerShell, stop only the dedicated
distribution, then reopen it:

```powershell
wsl --terminate Ubuntu-24.04
wsl --distribution Ubuntu-24.04
```

Replace `Ubuntu-24.04` if you chose another name. Inside Linux, verify:

```bash
findmnt -t drvfs,9p
command -v cmd.exe
systemctl is-active docker
```

The first two commands should not report mounted Windows drives or a Windows
command executable. A nonzero exit status with no match is expected. Check
`/etc/fstab` as well if your distribution has custom Windows drive mounts.
Disabling automount does not remove mounts explicitly configured elsewhere.

Clone Habitat and your project into separate folders under your Linux home
directory. Follow the [main README](../README.md). Keep this WSL terminal open
while you work. Agent authentication may need a URL or code opened manually in
your Windows browser because executable integration is disabled.

## Memory and stopping

The optional [host memory example](../examples/wslconfig.example) limits WSL2
memory to 4 GB. Settings in `%UserProfile%\.wslconfig` affect all WSL2
distributions. Merge them deliberately with your existing configuration, and
follow Microsoft's restart guidance. Habitat never edits this file.

When finished, run `bash habitat.sh stop` inside the Habitat checkout. Exit the
Linux shell, then run `wsl --terminate` for only this dedicated distribution.
This keeps the distribution, project files, images, and login volumes on disk.
