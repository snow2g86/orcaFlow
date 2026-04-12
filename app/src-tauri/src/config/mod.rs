//! 앱 전역 설정과 상태.
//!
//! `AppState` 는 Tauri 의 `State<'_, AppState>` 로 주입되어 모든 커맨드가
//! 공유하는 가변 상태를 담는다. M1 에서는 sidecar 브리지 참조만 보관.

use std::sync::Arc;

use directories::ProjectDirs;
use parking_lot::RwLock;
use serde::Serialize;

use crate::bridge::SidecarBridge;

#[derive(Debug, Clone, Serialize)]
pub struct AppPaths {
    pub workspace: String,
    pub logs_dir: String,
    pub db_path: String,
}

impl AppPaths {
    pub fn resolve() -> Self {
        let home = ProjectDirs::from("ai", "orcaflow", "OrcaFlow");
        let workspace = home
            .as_ref()
            .map(|p| p.data_dir().to_path_buf())
            .unwrap_or_else(|| std::env::temp_dir().join("orcaflow"));

        let logs_dir = workspace.join("logs");
        let db_path = workspace.join("db.sqlite");

        Self {
            workspace: workspace.to_string_lossy().into_owned(),
            logs_dir: logs_dir.to_string_lossy().into_owned(),
            db_path: db_path.to_string_lossy().into_owned(),
        }
    }
}

pub struct AppState {
    pub paths: AppPaths,
    pub bridge: Arc<RwLock<SidecarBridge>>,
}

impl AppState {
    pub fn new(bridge: Arc<RwLock<SidecarBridge>>) -> Self {
        Self {
            paths: AppPaths::resolve(),
            bridge,
        }
    }
}
