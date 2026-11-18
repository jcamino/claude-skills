# Type text into whatever has keyboard focus, as real OS keystrokes with small gaps.
# Used for the iCloud Passwords unlock code. uiautomation's own SendKeys leaves the
# extension's code boxes empty; Windows Forms SendKeys lands.
param([Parameter(Mandatory)][string]$Text, [switch]$Enter)

Add-Type -AssemblyName System.Windows.Forms
$rand = [System.Random]::new()
foreach ($ch in $Text.ToCharArray()) {
    $k = [string]$ch
    if ('+^%~(){}[]'.Contains($k)) { $k = '{' + $k + '}' }
    [System.Windows.Forms.SendKeys]::SendWait($k)
    Start-Sleep -Milliseconds (70 + $rand.Next(0, 110))
}
if ($Enter) { Start-Sleep -Milliseconds 200; [System.Windows.Forms.SendKeys]::SendWait('{ENTER}') }
"typed $($Text.Length) chars"
