// threads-intake configuration
// clientId: filled after Entra app registration (public by design for SPA).
export const CONFIG = {
  clientId: "REPLACE_WITH_CLIENT_ID",
  authority: "https://login.microsoftonline.com/alma01.com",
  scopes: ["Files.ReadWrite", "User.Read"],
  // OneDrive for Business path, relative to drive root. ASCII filenames only (vault iron rule).
  inboxPath: "Alma Mind/Alma.Threads/00-raw/inbox",
  mediaSubfolder: "media",
  // Simple PUT limit; above this we use an upload session (resumable).
  smallUploadLimit: 3.5 * 1024 * 1024,
};
