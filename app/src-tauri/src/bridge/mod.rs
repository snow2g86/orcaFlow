//! Tauri 셸 ↔ Python sidecar 브리지.

pub mod client;
pub mod sidecar;

pub use client::SidecarClient;
pub use sidecar::{Handshake, SidecarBridge, SidecarStatus};
