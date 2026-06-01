param(
  [ValidateSet("", "example", "post", "update")]
  [string]$Type = "",

  [string]$Theme = "",
  [string]$Title = "",
  [string]$Gpt = "",
  [string]$ImageUrl = "",
  [string]$Prompt = "",
  [string]$Good = "",
  [string]$Bad = "",
  [string]$Threads = "",
  [string]$Note = "",
  [switch]$FromClipboard
)

$ErrorActionPreference = "Stop"

function Ask-IfEmpty([string]$Value, [string]$Label) {
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return Read-Host $Label
  }
  return $Value
}

function Ask-Optional([string]$Value, [string]$Label, [string]$Default = "未設定") {
  if ([string]::IsNullOrWhiteSpace($Value)) {
    $inputValue = Read-Host "$Label（空Enterで$Default）"
    if ([string]::IsNullOrWhiteSpace($inputValue)) {
      return $Default
    }
    return $inputValue
  }
  return $Value
}

function Ask-LongText([string]$Value, [string]$Label) {
  if (-not [string]::IsNullOrWhiteSpace($Value)) {
    return $Value
  }

  if ($FromClipboard) {
    $clip = Get-Clipboard -Raw
    if (-not [string]::IsNullOrWhiteSpace($clip)) {
      return $clip.Trim()
    }
  }

  $useClipboard = Read-Host "$Label は複数行になりやすいです。クリップボードから読み込みますか？ y/N"
  if ($useClipboard -eq "y" -or $useClipboard -eq "Y") {
    $clip = Get-Clipboard -Raw
    if (-not [string]::IsNullOrWhiteSpace($clip)) {
      return $clip.Trim()
    }
    Write-Host "クリップボードが空でした。1行で入力してください。"
  }

  return Read-Host "$Label を入力してください"
}

function Slugify([string]$Text) {
  $slug = $Text.ToLowerInvariant()
  $slug = $slug -replace '[\\/:*?"<>|]', ''
  $slug = $slug -replace '\s+', '-'
  $slug = $slug -replace '-+', '-'
  $slug = $slug.Trim('-')
  if ([string]::IsNullOrWhiteSpace($slug)) {
    return "untitled"
  }
  return $slug
}

function Ensure-Dir([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

if ([string]::IsNullOrWhiteSpace($PSCommandPath) -and -not [string]::IsNullOrWhiteSpace($env:MVG_SCRIPT_PATH)) {
  $ScriptPath = $env:MVG_SCRIPT_PATH
} else {
  $ScriptPath = $PSCommandPath
}

$Root = Split-Path -Parent (Split-Path -Parent $ScriptPath)
$Today = Get-Date -Format "yyyy-MM-dd"
$Stamp = Get-Date -Format "yyyyMMdd-HHmm"

if ([string]::IsNullOrWhiteSpace($Type)) {
  Write-Host "作成するメモの種類を選んでください。"
  Write-Host "1: 作例メモ"
  Write-Host "2: Threads投稿メモ"
  Write-Host "3: GPT更新メモ"
  $Choice = Read-Host "番号"
  switch ($Choice) {
    "1" { $Type = "example" }
    "2" { $Type = "post" }
    "3" { $Type = "update" }
    default { $Type = "example" }
  }
}

switch ($Type) {
  "example" {
    $Theme = Ask-IfEmpty $Theme "テーマを入力してください（例: 褥瘡、転倒予防、心不全リハなど。自由入力）"
    $Title = Ask-IfEmpty $Title "タイトルを入力してください"
    $Gpt = Ask-IfEmpty $Gpt "使ったGPTを入力してください"
    $ImageUrl = Ask-Optional $ImageUrl "画像URLまたは保存場所"
    $Prompt = Ask-LongText $Prompt "使ったプロンプト"
    $Good = Ask-IfEmpty $Good "よかった点を入力してください"
    $Bad = Ask-IfEmpty $Bad "失敗した点を入力してください"
    $Threads = Ask-LongText $Threads "Threads投稿文"
    $Note = Ask-IfEmpty $Note "note導線を入力してください"

    $ThemeSlug = Slugify $Theme
    $TitleSlug = Slugify $Title
    $Dir = Join-Path $Root "examples\$ThemeSlug"
    Ensure-Dir $Dir
    $Path = Join-Path $Dir "$Today-$TitleSlug.md"

    $Content = @"
# 作例メモ

日付: $Today
テーマ: $Theme
タイトル: $Title
使ったGPT: $Gpt
画像URL: $ImageUrl

## 使ったプロンプト

~~~text
$Prompt
~~~

## よかった点

$Good

## 失敗した点

$Bad

## Threads投稿文

~~~text
$Threads
~~~

## note導線

$Note

## あとで見返すメモ

- 医療安全で気になる点:
- 次回も使いたい成功パターン:
- GPT Instructionsへ反映したいこと:
"@
  }

  "post" {
    $Threads = Ask-LongText $Threads "Threads投稿文"
    $ImageUrl = Ask-Optional $ImageUrl "画像URLまたは保存場所"
    $Note = Ask-Optional $Note "note導線"

    $Dir = Join-Path $Root "posts"
    Ensure-Dir $Dir
    $PostId = "th-$Stamp"
    $Path = Join-Path $Dir "$Today-$PostId.md"

    $Content = @"
# Threads投稿メモ

日付: $Today
投稿ID: $PostId
状態: draft
画像URL: $ImageUrl

## 投稿文

~~~text
$Threads
~~~

## note導線

$Note

## 投稿後メモ

- 投稿URL:
- 反応:
- 次回改善:
"@
  }

  "update" {
    $Title = Ask-IfEmpty $Title "更新タイトルを入力してください"
    $Gpt = Ask-IfEmpty $Gpt "対象GPTを入力してください"
    $Good = Ask-IfEmpty $Good "何を変えたか入力してください"
    $Bad = Ask-IfEmpty $Bad "リスクや不安点を入力してください"

    $Dir = Join-Path $Root "update-logs"
    Ensure-Dir $Dir
    $Path = Join-Path $Dir "$Today-$(Slugify $Title).md"

    $Content = @"
# GPT更新メモ

日付: $Today
対象GPT: $Gpt
更新タイトル: $Title
状態: draft

## 何を変えたか

$Good

## リスクや不安点

$Bad

## 医療安全チェック

- [ ] 診断・治療の代替に見えない
- [ ] 治療効果を断定していない
- [ ] 医療者確認の余地がある
- [ ] 公開リスクが高い表現を確認した

## 公開前メモ

- 期待する効果:
- 戻す条件:
- 次回確認:
"@
  }
}

Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
Write-Host "作成しました: $Path"
