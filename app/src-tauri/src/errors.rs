//! Tauri shell의 공통 에러 타입.
//!
//! 모든 커맨드는 `Result<T, OrcaError>` 를 반환하고, serde 를 통해
//! Frontend 로 직렬화된다 (`code`, `message`, `details`).

use serde::{Serialize, Serializer};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum OrcaError {
    #[error("{0}")]
    Config(String),

    #[error("sidecar not ready: {0}")]
    SidecarNotReady(String),

    #[error("sidecar request failed: {0}")]
    SidecarHttp(String),

    #[error("{0}")]
    Internal(String),
}

impl OrcaError {
    pub fn code(&self) -> &'static str {
        match self {
            OrcaError::Config(_) => "config.invalid",
            OrcaError::SidecarNotReady(_) => "sidecar.not_ready",
            OrcaError::SidecarHttp(_) => "sidecar.http_error",
            OrcaError::Internal(_) => "orca.unknown",
        }
    }
}

impl Serialize for OrcaError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        use serde::ser::SerializeStruct;
        let mut state = serializer.serialize_struct("OrcaError", 2)?;
        state.serialize_field("code", self.code())?;
        state.serialize_field("message", &self.to_string())?;
        state.end()
    }
}

impl From<anyhow::Error> for OrcaError {
    fn from(e: anyhow::Error) -> Self {
        OrcaError::Internal(e.to_string())
    }
}

impl From<std::io::Error> for OrcaError {
    fn from(e: std::io::Error) -> Self {
        OrcaError::Internal(e.to_string())
    }
}

impl From<reqwest::Error> for OrcaError {
    fn from(e: reqwest::Error) -> Self {
        OrcaError::SidecarHttp(e.to_string())
    }
}

pub type OrcaResult<T> = std::result::Result<T, OrcaError>;
