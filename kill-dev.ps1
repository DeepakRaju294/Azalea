$ports = @(8000, 3000)

foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $procId = $conn.OwningProcess
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Killing $($proc.Name) (PID $procId) on port $port"
            Stop-Process -Id $procId -Force
        }
    } else {
        Write-Host "Nothing on port $port"
    }
}
