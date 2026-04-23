import { BrowserRouter } from "react-router-dom";

import { WorkspaceShell } from "./layout/WorkspaceShell";
import { StreamJobsProvider } from "./context/StreamJobsContext";

export default function App() {
  return (
    <BrowserRouter>
      <StreamJobsProvider>
        <WorkspaceShell />
      </StreamJobsProvider>
    </BrowserRouter>
  );
}
