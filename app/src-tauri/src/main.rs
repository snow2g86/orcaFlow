// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::Command;
use std::sync::Arc;

use parking_lot::RwLock;
use tracing::{error, info};
use tracing_subscriber::EnvFilter;

use orcaflow_lib::bridge::SidecarBridge;
use orcaflow_lib::config::AppState;

fn init_tracing() {
    let filter = EnvFilter::try_from_env("ORCA_LOG").unwrap_or_else(|_| EnvFilter::new("info"));
    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(true)
        .json()
        .try_init()
        .ok();
}

fn build_sidecar_command() -> Command {
    if std::env::var("ORCA_DEV").is_ok() {
        // 개발 모드: uv run python -m orca_core
        let repo_sidecar: PathBuf = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../sidecar")
            .canonicalize()
            .unwrap_or_else(|_| PathBuf::from("../sidecar"));

        let mut cmd = Command::new("uv");
        cmd.arg("run")
            .arg("python")
            .arg("-m")
            .arg("orca_core")
            .current_dir(repo_sidecar);
        cmd
    } else {
        // 프로덕션 모드: 번들된 PyInstaller 바이너리
        let exe_dir = std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.to_path_buf()))
            .unwrap_or_else(|| PathBuf::from("."));

        #[cfg(target_os = "windows")]
        let sidecar_name = "orca-sidecar.exe";
        #[cfg(not(target_os = "windows"))]
        let sidecar_name = "orca-sidecar";

        // Tauri externalBin 은 실행 파일 옆에 바이너리를 배치한다
        let sidecar_path = exe_dir.join(sidecar_name);
        info!(
            event = "sidecar.resolve",
            mode = "production",
            path = %sidecar_path.display(),
        );
        Command::new(sidecar_path)
    }
}

fn main() {
    init_tracing();

    let bridge = Arc::new(RwLock::new(SidecarBridge::default()));

    // sidecar 기동 (실패해도 앱은 뜨되 상태가 Failed 로 노출됨)
    {
        let mut b = bridge.write();
        if let Err(err) = b.spawn(build_sidecar_command()) {
            error!(event = "sidecar.spawn_failed", "{err}");
            b.status = orcaflow_lib::bridge::SidecarStatus::Failed {
                reason: err.to_string(),
            };
        }
    }

    let state = AppState::new(bridge.clone());
    info!(event = "app.starting", workspace = %state.paths.workspace);

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .manage(state)
        .invoke_handler(tauri::generate_handler![orcaflow_lib::commands::health::app_ready, orcaflow_lib::commands::config::config_get])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
