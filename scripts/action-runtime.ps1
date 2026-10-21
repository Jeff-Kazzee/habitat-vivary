# Native hosted jobs only. Review immutable action manifests for pre hooks before use.
# No run step can precede action pre hooks, runner job hooks or early hashFiles().
# Any failure/always diagnostic action must also require this step's success.
# Floors: https://nodejs.org/en/blog/vulnerability/october-2026-security-releases
# Expiry uses the schedule end date as an exclusive UTC cutoff, without an extra day.
# https://github.com/nodejs/Release/blob/main/schedule.json
$ErrorActionPreference = 'Stop'

function Assert-ActionNodeVersion {
  param([string]$Runtime, [string]$Version, [datetime]$AsOf = [datetime]::UtcNow)
  $match = [regex]::Match($Version, '\A24\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\z')
  if ($Runtime -cne 'node24' -or -not $match.Success) {
    throw 'CI_UNSUPPORTED_ACTION_RUNTIME: require a reviewed stable node24 interpreter; EOL, unknown and custom runtimes are refused.'
  }
  $minor = [int]$match.Groups[1].Value
  $patch = [int]$match.Groups[2].Value
  if ($minor -lt 22 -or ($minor -eq 22 -and $patch -lt 1) -or $AsOf.ToUniversalTime() -ge [datetime]::new(2028,4,30,0,0,0,[DateTimeKind]::Utc)) {
    throw "CI_UNSUPPORTED_ACTION_RUNTIME: node24 requires Node 24.22.1 or later before its 2028-04-30 UTC expiry; received $Version. Use a patched provider image. Do not substitute PATH Node or waive a provider backport without evidence."
  }
}

function Read-BoundedProbeText {
  param([IO.Stream]$Stream, [datetime]$Deadline)
  $buffer = [byte[]]::new(4097)
  $used = 0
  do {
    $remaining = [int]($Deadline - [datetime]::UtcNow).TotalMilliseconds
    if ($remaining -le 0) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: interpreter output timed out.' }
    $read = $Stream.ReadAsync($buffer, $used, $buffer.Length - $used)
    if (-not $read.Wait($remaining)) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: interpreter output timed out.' }
    $count = $read.Result
    $used += $count
  } while ($count -gt 0 -and $used -lt $buffer.Length)
  if ($used -gt 4096) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: oversized interpreter output.' }
  return [Text.UTF8Encoding]::new($false, $true).GetString($buffer, 0, $used)
}

function Get-BundledNodeInfo {
  param([string]$Executable)
  $start = [Diagnostics.ProcessStartInfo]::new($Executable)
  $start.UseShellExecute = $false
  $start.RedirectStandardOutput = $true
  $start.RedirectStandardError = $true
  $start.ArgumentList.Add('--eval')
  $start.ArgumentList.Add('process.stdout.write(JSON.stringify({version:process.versions.node,execPath:process.execPath}))')
  $probe = [Diagnostics.Process]::new()
  $probe.StartInfo = $start
  $deadline = [datetime]::UtcNow.AddSeconds(5)
  $started = $false
  try {
    $started = $probe.Start()
    if (-not $started -or -not $probe.WaitForExit(5000)) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: interpreter probe timed out.' }
    $output = Read-BoundedProbeText $probe.StandardOutput.BaseStream $deadline
    $errors = Read-BoundedProbeText $probe.StandardError.BaseStream $deadline
    if ($probe.ExitCode -ne 0 -or $errors.Length -ne 0) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: interpreter probe failed or emitted diagnostics.' }
    $info = ConvertFrom-Json -InputObject $output -AsHashtable
    if ($info.version -isnot [string] -or $info.execPath -isnot [string]) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: malformed interpreter identity.' }
    $comparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    if (-not [string]::Equals([IO.Path]::GetFullPath($Executable), [IO.Path]::GetFullPath($info.execPath), $comparison)) {
      throw 'CI_UNSUPPORTED_ACTION_RUNTIME: interpreter identity does not match the bundled executable.'
    }
    return $info
  } finally {
    try {
      if ($started -and -not $probe.HasExited) { $probe.Kill($true); $probe.WaitForExit(1000) | Out-Null }
    } finally { $probe.Dispose() }
  }
}

function Assert-RunnerActionRuntimes {
  param([string[]]$Runtimes)
  if (-not $Runtimes -or @($Runtimes | Where-Object { $_ -cne 'node24' }).Count) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: only explicitly reviewed node24 actions are supported; node20 is EOL.' }
  $hostOS = if ($IsWindows) { 'Windows' } elseif ($IsLinux) { 'Linux' } elseif ($IsMacOS) { 'macOS' } else { '' }
  if ($env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or $env:RUNNER_OS -cne $hostOS -or $env:RUNNER_ARCH -notin @('X64','ARM64')) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: unsupported hosted platform.' }
  $unsafe = @(Get-ChildItem Env: | Where-Object {
    $_.Value -and ($_.Name -in @('NODE_OPTIONS','ACTIONS_RUNNER_FORCE_ACTIONS_NODE_VERSION','ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION','ACTIONS_RUNNER_HOOK_JOB_STARTED','ACTIONS_RUNNER_HOOK_JOB_COMPLETED') -or $_.Name -match '\AFORCE_JAVASCRIPT_ACTIONS_TO_NODE[0-9]+\z')
  })
  if ($unsafe.Count) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: unreviewed Node options, migration override or runner hook. Refuse without printing its value.' }
  $workers = @(Get-Process -Name 'Runner.Worker' -ErrorAction Stop)
  if ($workers.Count -ne 1) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: missing or ambiguous Runner.Worker.' }
  $ancestor = Get-Process -Id $PID -ErrorAction Stop
  $owned = $false
  for ($depth = 0; $ancestor -and $depth -lt 16; $depth++) {
    if ($ancestor.Id -eq $workers[0].Id) { $owned = $true; break }
    $ancestor = $ancestor.Parent
  }
  if (-not $owned) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: Runner.Worker is not a verified ancestor.' }
  $workerPath = $workers[0].Path
  $workerName = if ($IsWindows) { 'Runner.Worker.exe' } else { 'Runner.Worker' }
  if (-not $workerPath -or -not [IO.Path]::IsPathFullyQualified($workerPath) -or [IO.Path]::GetFileName($workerPath) -cne $workerName) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: unreadable native worker path.' }
  $bin = [IO.Path]::GetDirectoryName($workerPath)
  if ([IO.Path]::GetFileName($bin) -cne 'bin' -or -not [IO.File]::Exists((Join-Path $bin 'Runner.Worker.dll'))) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: unfamiliar worker layout.' }
  $runnerRoot = [IO.Path]::GetDirectoryName($bin)
  foreach ($runtime in @($Runtimes | Select-Object -Unique)) {
    $nodeName = if ($IsWindows) { 'node.exe' } else { 'node' }
    $executable = Join-Path $runnerRoot "externals/$runtime/bin/$nodeName"
    if (-not [IO.File]::Exists($executable)) { throw 'CI_UNSUPPORTED_ACTION_RUNTIME: bundled action interpreter is missing.' }
    $info = Get-BundledNodeInfo $executable
    Assert-ActionNodeVersion $runtime $info.version
    Write-Output "Verified bundled action interpreter: $executable Node $($info.version)"
  }
}

# Enumerate every effective JavaScript action runtime from the reviewed manifests.
Assert-RunnerActionRuntimes -Runtimes @('node24')
