param(
    [int]$Port = 8081,
    [ValidateRange(0, 99)][int]$GpuLayers = 99
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $projectRoot '.cache\llama-cpp\b12613\llama-server.exe'
$modelDirectory = Join-Path $projectRoot '.cache\local-models\qwen3-vl-8b'
$weightsPath = Join-Path $modelDirectory 'Qwen3VL-8B-Instruct-Q4_K_M.gguf'
$visionPath = Join-Path $modelDirectory 'mmproj-Qwen3VL-8B-Instruct-F16.gguf'
foreach ($requiredPath in @($runtimePath, $weightsPath, $visionPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Missing $requiredPath. Run python tools/setup_local_model.py first."
    }
}
& $runtimePath --model $weightsPath --mmproj $visionPath --host 127.0.0.1 --port $Port `
    --alias qwen3-vl-8b-local --ctx-size 8192 --parallel 1 --n-gpu-layers $GpuLayers `
    --batch-size 512 --ubatch-size 128 --flash-attn on --jinja --no-webui `
    --image-min-tokens 1024 --image-max-tokens 2048 --cors-origins localhost
exit $LASTEXITCODE
