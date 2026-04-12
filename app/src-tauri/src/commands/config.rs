//! `config_get` — sidecar /config 엔드포인트 프록시.

use serde_json::Value;

use crate::config::AppState;
use crate::errors::{OrcaError, OrcaResult};

#[tauri::command]
pub async fn config_get(state: tauri::State<'_, AppState>) -> OrcaResult<Value> {
    let client = {
        let bridge = state.bridge.read();
        bridge
            .client()
            .cloned()
            .ok_or_else(|| OrcaError::SidecarNotReady("sidecar client unavailable".into()))?
    };

    client.get_json::<Value>("/config").await
}
