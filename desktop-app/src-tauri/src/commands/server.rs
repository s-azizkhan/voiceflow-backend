use std::process::Stdio;

const SERVER_PORT: u16 = 8765;

#[tauri::command]
pub async fn check_server_health() -> Result<bool, String> {
    let url = format!("http://localhost:{}/health", SERVER_PORT);
    match reqwest::get(&url).await {
        Ok(resp) => Ok(resp.status().is_success()),
        Err(e) => {
            tracing::warn!("Server health check failed: {}", e);
            Ok(false)
        }
    }
}

#[tauri::command]
pub async fn start_server() -> Result<(), String> {
    // Check if already running
    if check_server_health().await.unwrap_or(false) {
        tracing::info!("VoiceFlow server already running on port 8765");
        return Ok(());
    }

    // Find the Python server script relative to this binary
    let exe_path = std::env::current_exe().map_err(|e| e.to_string())?;
    // In dev: target/release/voiceflow -> project root
    // In bundle: Contents/MacOS/VoiceFlow -> Contents/Resources
    let script_path = exe_path
        .parent()
        .and_then(|p| p.parent()) // Contents/MacOS
        .and_then(|p| p.parent()) // Contents
        .and_then(|p| p.parent()) // VoiceFlow.app
        .map(|p| p.join("Contents/Resources/server.py"))
        .or_else(|| exe_path.parent().map(|p| p.join("server.py")))
        .unwrap_or_else(|| "server.py".into());

    tracing::info!("Starting server from: {:?}", script_path);

    let mut child = tokio::process::Command::new("python3")
        .arg(&script_path)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to spawn server: {}", e))?;

    // Wait for server to be ready (max 15s)
    for _ in 0..30 {
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        if check_server_health().await.unwrap_or(false) {
            tracing::info!("VoiceFlow server started successfully");
            return Ok(());
        }
    }

    // Kill child if it failed to start
    child.kill().await.ok();
    Err("Server failed to start within timeout".to_string())
}
