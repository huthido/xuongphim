<#
Tạo video clip ngắn từ lời mô tả bằng Wan2.1-T2V-1.3B + CausVid (4 bước) qua stable-diffusion.cpp (Vulkan).
Chạy được trên GPU AMD Radeon, Intel, NVIDIA. Xem HUONG_DAN_CAI_TAO_VIDEO_AMD.md.

  Một clip:   powershell -ExecutionPolicy Bypass -File tao_video_amd.ps1 -Prompt "..." -Out clip.mp4 [-W 832 -H 480] [-Frames 33] [-Seed 7]
  Nhiều clip: powershell -ExecutionPolicy Bypass -File tao_video_amd.ps1 -Jobs viec.json
              (danh sách {"prompt", "out", "w"?, "h"?, "frames"?, "seed"?}; clip đã có thì bỏ qua trừ khi thêm -Overwrite)
  -Cpu        chạy bằng CPU thay vì GPU (rất chậm, chỉ để thử)
  -VaeDayDu   giải mã bằng VAE gốc của Wan thay cho TAEHV (đúng nhất nhưng chậm hơn nhiều lần)
  -Extra      tham số thêm cho sd-cli, ví dụ -Extra "--offload-to-cpu" khi GPU báo thiếu bộ nhớ
#>
param(
    [string]$Prompt,
    [string]$Out,
    [string]$Jobs,
    [int]$W = 832,
    [int]$H = 480,
    [int]$Frames = 33,
    [int]$Fps = 16,
    [int]$Seed = 7,
    [int]$Steps = 4,
    [switch]$Cpu,
    [switch]$VaeDayDu,
    [string[]]$Extra = @(),
    [switch]$Overwrite
)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$sd = Join-Path $here "sd\sd-cli.exe"
$m = Join-Path $here "models"
$lora = "Wan21_CausVid_bidirect2_T2V_1_3B_lora_rank32"

$ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
if (-not $ffmpeg) {
    $ffmpeg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\ffmpeg.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $ffmpeg) { throw "khong tim thay ffmpeg; cai bang: winget install --id Gyan.FFmpeg -e" }

if ($Jobs) {
    $list = @(Get-Content $Jobs -Raw -Encoding UTF8 | ConvertFrom-Json)
} elseif ($Prompt -and $Out) {
    $list = @([pscustomobject]@{ prompt = $Prompt; out = $Out })
} else {
    throw "can -Prompt va -Out, hoac -Jobs"
}
$list = @($list | Where-Object { $Overwrite -or -not (Test-Path $_.out) })
if ($list.Count -eq 0) { Write-Output "khong con clip nao phai tao"; exit 0 }

foreach ($j in $list) {
    $w = if ($j.w) { [int]$j.w } else { $W }
    $h = if ($j.h) { [int]$j.h } else { $H }
    $gw = [math]::Ceiling($w / 16) * 16  # mô hình cần cạnh chia hết cho 16
    $gh = [math]::Ceiling($h / 16) * 16
    $n = if ($j.frames) { [int]$j.frames } else { $Frames }
    $s = if ($j.seed) { [int]$j.seed } else { $Seed }
    $out = [System.IO.Path]::GetFullPath($j.out)
    New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
    $tmp = Join-Path $env:TEMP ("tao_video_amd_{0}.webm" -f $PID)

    $sdArgs = @("-M", "vid_gen",
        "--diffusion-model", "$m\wan2.1_t2v_1.3B_fp16.safetensors",
        "--t5xxl", "$m\umt5-xxl-encoder-Q5_K_M.gguf",
        "--lora-model-dir", "$m\loras",
        "-p", ("{0}<lora:{1}:0.95>" -f $j.prompt.Replace('"', "'"), $lora),
        "--cfg-scale", "1.0", "--sampling-method", "euler", "--steps", "$Steps", "--flow-shift", "3.0",
        "-W", "$gw", "-H", "$gh", "--video-frames", "$n", "--fps", "$Fps", "--seed", "$s",
        "--vae-tiling", "-o", $tmp)
    # TAEHV (taew2_1) giải mã nhanh hơn VAE gốc khoảng 20 lần, hình gần như giống hệt
    if ($VaeDayDu) { $sdArgs += @("--vae", "$m\wan_2.1_vae.safetensors") } else { $sdArgs += @("--tae", "$m\taew2_1.safetensors") }
    if ($Cpu) { $sdArgs += @("--backend", "cpu") }
    $sdArgs += $Extra

    $t = Get-Date
    & $sd @sdArgs
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $tmp)) { throw "sd-cli loi (ma $LASTEXITCODE) khi tao $out" }

    $vf = "crop=${w}:${h}"  # cắt về đúng cỡ đã xin nếu phải làm tròn lên
    & $ffmpeg -v error -y -i $tmp -vf $vf -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart $out
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg loi khi ghi $out" }
    Remove-Item $tmp
    $sec = [int]((Get-Date) - $t).TotalSeconds
    Write-Output ("OK {0}  {1}x{2}  {3} khung = {4:N1}s  {5}s" -f $out, $w, $h, $n, ($n / $Fps), $sec)
}
