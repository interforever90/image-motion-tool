param([Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class WindowCapture {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr window, out RECT rect);
    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr window, IntPtr dc, uint flags);
}
'@
$window = Get-Process ImageMotionTool | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $window) { throw 'Application window not found for screenshot' }
$rect = New-Object WindowCapture+RECT
if (-not [WindowCapture]::GetWindowRect($window.MainWindowHandle, [ref]$rect)) { throw 'GetWindowRect failed' }
$bitmap = New-Object System.Drawing.Bitmap(($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top))
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $dc = $graphics.GetHdc()
    try {
        if (-not [WindowCapture]::PrintWindow($window.MainWindowHandle, $dc, 0)) { throw 'PrintWindow failed' }
    } finally { $graphics.ReleaseHdc($dc) }
    $bitmap.Save([System.IO.Path]::GetFullPath($Output), [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}
