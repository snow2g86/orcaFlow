//! Python sidecar 프로세스 감독자.
//!
//! - sidecar 를 자식 프로세스로 spawn
//! - stdout 첫 줄의 handshake JSON 파싱 (OrcaFlow.do.md §2.3)
//! - 포트/토큰을 저장하고 `SidecarClient` 생성
//! - 이후 stdout/stderr 는 로그로 릴레이
//!
//! 재시작/헬스체크/graceful shutdown 은 M1+α 에서 확장.

use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::thread;

use serde::{Deserialize, Serialize};
use tracing::{error, info, warn};

use crate::bridge::SidecarClient;
use crate::errors::{OrcaError, OrcaResult};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Handshake {
    pub kind: String,
    pub port: u16,
    pub token: String,
    pub pid: u32,
    pub version: String,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "snake_case", tag = "state")]
pub enum SidecarStatus {
    Starting,
    Ready {
        port: u16,
        version: String,
        token: String,
    },
    Failed {
        reason: String,
    },
}

impl std::fmt::Debug for SidecarStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Starting => f.write_str("Starting"),
            Self::Ready { port, version, .. } => f
                .debug_struct("Ready")
                .field("port", port)
                .field("version", version)
                .field("token", &"***")
                .finish(),
            Self::Failed { reason } => f
                .debug_struct("Failed")
                .field("reason", reason)
                .finish(),
        }
    }
}

pub struct SidecarBridge {
    pub status: SidecarStatus,
    child: Option<Child>,
    client: Option<SidecarClient>,
}

impl Default for SidecarBridge {
    fn default() -> Self {
        Self {
            status: SidecarStatus::Starting,
            child: None,
            client: None,
        }
    }
}

impl SidecarBridge {
    /// sidecar 프로세스를 기동하고 handshake 를 수신한다.
    ///
    /// `command` 는 `python -m orca_core` 또는 PyInstaller 번들 경로.
    pub fn spawn(&mut self, mut command: Command) -> OrcaResult<()> {
        command.stdout(Stdio::piped()).stderr(Stdio::piped());

        let mut child = command
            .spawn()
            .map_err(|e| OrcaError::SidecarNotReady(format!("spawn failed: {e}")))?;

        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| OrcaError::SidecarNotReady("no stdout".into()))?;

        let mut reader = BufReader::new(stdout);
        let mut first_line = String::new();
        reader
            .read_line(&mut first_line)
            .map_err(|e| OrcaError::SidecarNotReady(format!("handshake read failed: {e}")))?;

        let handshake: Handshake = serde_json::from_str(first_line.trim())
            .map_err(|e| OrcaError::SidecarNotReady(format!("handshake parse failed: {e}")))?;

        if handshake.kind != "handshake" {
            return Err(OrcaError::SidecarNotReady(format!(
                "unexpected handshake kind: {}",
                handshake.kind
            )));
        }

        // 이후 stdout 라인은 별도 스레드에서 로그로 릴레이
        thread::spawn(move || {
            for line in reader.lines().map_while(Result::ok) {
                info!(target: "sidecar.stdout", "{line}");
            }
        });

        if let Some(stderr) = child.stderr.take() {
            thread::spawn(move || {
                for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                    warn!(target: "sidecar.stderr", "{line}");
                }
            });
        }

        let client = SidecarClient::new(handshake.port, handshake.token.clone())?;
        self.client = Some(client);
        self.status = SidecarStatus::Ready {
            port: handshake.port,
            version: handshake.version.clone(),
            token: handshake.token.clone(),
        };
        self.child = Some(child);

        info!(
            event = "sidecar.ready",
            port = handshake.port,
            version = %handshake.version,
            "sidecar handshake complete"
        );

        Ok(())
    }

    pub fn client(&self) -> Option<&SidecarClient> {
        self.client.as_ref()
    }

    pub fn shutdown(&mut self) {
        if let Some(mut child) = self.child.take() {
            if let Err(e) = child.kill() {
                error!("sidecar kill failed: {e}");
            }
            let _ = child.wait();
        }
    }
}

impl Drop for SidecarBridge {
    fn drop(&mut self) {
        self.shutdown();
    }
}
