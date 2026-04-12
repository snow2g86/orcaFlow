//! Frontend 가 호출하는 Tauri 커맨드 집합 (design.md §4.1).
//!
//! M1 범위: `app_ready`, `config_get` 만 노출.

pub mod config;
pub mod health;

pub use config::config_get;
pub use health::app_ready;
