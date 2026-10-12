param([switch]$RefreshFonts)

$ErrorActionPreference = 'Stop'
$productionRoot = Split-Path -Parent $PSScriptRoot
$assetRoot = Join-Path $productionRoot 'public'
$rawAudioRoot = Join-Path $productionRoot 'work/audio/raw'
New-Item -ItemType Directory -Force -Path (Join-Path $assetRoot 'fonts'),$rawAudioRoot,(Join-Path $productionRoot 'licenses') | Out-Null
$fontFiles = @(
    @('spacegrotesk','SpaceGrotesk[wght].ttf','SpaceGrotesk.ttf'),
    @('inter','Inter[opsz,wght].ttf','Inter.ttf'),
    @('ibmplexmono','IBMPlexMono-Regular.ttf','IBMPlexMono.ttf')
)
foreach ($font in $fontFiles) {
    if (!$RefreshFonts -and (Test-Path -LiteralPath (Join-Path $assetRoot ('fonts/' + $font[2])))) { continue }
    $fontUrl = 'https://raw.githubusercontent.com/google/fonts/main/ofl/' + $font[0] + '/' + [Uri]::EscapeDataString($font[1])
    Invoke-WebRequest -Uri $fontUrl -OutFile (Join-Path $assetRoot ('fonts/' + $font[2]))
    Invoke-WebRequest -Uri ('https://raw.githubusercontent.com/google/fonts/main/ofl/' + $font[0] + '/OFL.txt') -OutFile (Join-Path $productionRoot ('licenses/' + $font[0] + '-OFL.txt'))
}
$storyboard = Get-Content -LiteralPath (Join-Path $productionRoot 'creative/storyboard.json') -Raw | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.SelectVoice('Microsoft David Desktop')
$voice.Rate = 0
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(48000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$manifest = @()
foreach ($scene in $storyboard.scenes) {
    $phrases = [regex]::Matches($scene.narration, '[^.!?]+[.!?]')
    $phraseIndex = 0
    foreach ($match in $phrases) {
        $text = $match.Value.Trim()
        $escaped = [System.Security.SecurityElement]::Escape($text)
        $escaped = $escaped.Replace('AgentForge','<sub alias="agent forge">AgentForge</sub>').Replace('PostgreSQL','<sub alias="post gres Q L">PostgreSQL</sub>')
        $ssml = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US"><prosody rate="+4%">' + $escaped + '</prosody></speak>'
        $filename = 'scene-' + $scene.id + '-phrase-' + $phraseIndex + '.wav'
        $voice.SetOutputToWaveFile((Join-Path $rawAudioRoot $filename), $format)
        $voice.SpeakSsml($ssml)
        $manifest += [pscustomobject]@{scene=$scene.id;phrase=$phraseIndex;text=$text;file=$filename}
        $phraseIndex++
    }
}
$voice.Dispose()
$manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $rawAudioRoot 'manifest.json') -Encoding utf8
Write-Output ('Prepared local fonts and ' + $manifest.Count + ' voiceover phrases in work/audio/raw/.')
