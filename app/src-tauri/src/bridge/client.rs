//! Sidecar HTTP 클라이언트.
//!
//! 모든 요청에 `X-Orca-Token` 헤더를 자동 주입한다. 토큰은 생성자에서만
//! 설정되고 외부로 노출되지 않는다 (로그에도 찍히면 안 됨).

use std::time::Duration;

use reqwest::header::{HeaderMap, HeaderValue};
use serde::de::DeserializeOwned;

use crate::errors::{OrcaError, OrcaResult};

const TOKEN_HEADER: &str = "X-Orca-Token";
const DEFAULT_TIMEOUT_SECS: u64 = 30;

#[derive(Clone)]
pub struct SidecarClient {
    base_url: String,
    inner: reqwest::Client,
}

impl std::fmt::Debug for SidecarClient {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SidecarClient")
            .field("base_url", &self.base_url)
            .field("token", &"***")
            .finish()
    }
}

impl SidecarClient {
    pub fn new(port: u16, token: String) -> OrcaResult<Self> {
        let mut headers = HeaderMap::new();
        let value = HeaderValue::from_str(&token)
            .map_err(|_| OrcaError::Internal("invalid sidecar token".into()))?;
        headers.insert(TOKEN_HEADER, value);

        let inner = reqwest::Client::builder()
            .default_headers(headers)
            .timeout(Duration::from_secs(DEFAULT_TIMEOUT_SECS))
            .build()
            .map_err(|e| OrcaError::Internal(format!("client build failed: {e}")))?;

        Ok(Self {
            base_url: format!("http://127.0.0.1:{port}"),
            inner,
        })
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub async fn get_json<T: DeserializeOwned>(&self, path: &str) -> OrcaResult<T> {
        let url = format!("{}{}", self.base_url, path);
        let response = self.inner.get(&url).send().await?;
        if !response.status().is_success() {
            return Err(OrcaError::SidecarHttp(format!(
                "{} returned {}",
                path,
                response.status()
            )));
        }
        let value = response.json::<T>().await?;
        Ok(value)
    }
}
