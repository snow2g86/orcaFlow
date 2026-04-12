//! `app_ready` — 앱 초기화 상태 조회.

use serde::Serialize;

use crate::bridge::SidecarStatus;
use crate::config::AppState;
use crate::errors::OrcaResult;

/// Frontend 가 sidecar 에 직접 HTTP 호출할 때 필요한 정보.
/// token 은 Debug 에서 마스킹한다.
#[derive(Clone, Serialize)]
pub struct SidecarEndpoint {
    pub port: u16,
    pub token: String,
    pub version: String,
}

impl std::fmt::Debug for SidecarEndpoint {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SidecarEndpoint")
            .field("port", &self.port)
            .field("token", &"***")
            .field("version", &self.version)
            .finish()
    }
}

#[derive(Debug, Serialize)]
pub struct AppStatus {
    pub sidecar: SidecarStatus,
    pub endpoint: Option<SidecarEndpoint>,
    pub workspace: String,
    pub version: String,
}

#[tauri::command]
pub async fn app_ready(state: tauri::State<'_, AppState>) -> OrcaResult<AppStatus> {
    let bridge = state.bridge.read();
    let endpoint = match &bridge.status {
        SidecarStatus::Ready {
            port,
            version,
            token,
        } => Some(SidecarEndpoint {
            port: *port,
            token: token.clone(),
            version: version.clone(),
        }),
        _ => None,
    };
    Ok(AppStatus {
        sidecar: bridge.status.clone(),
        endpoint,
        workspace: state.paths.workspace.clone(),
        version: env!("CARGO_PKG_VERSION").to_string(),
    })
}
