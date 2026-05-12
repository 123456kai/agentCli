import { ReactNode } from "react";

type WorkbenchShellProps = {
  title: string;
  repoLabel: string;
  modelLabel: string;
  status: string;
  sidebar: ReactNode;
  editor: ReactNode;
  inspector: ReactNode;
  statusbar: ReactNode;
};

export function WorkbenchShell({
  title,
  repoLabel,
  modelLabel,
  status,
  sidebar,
  editor,
  inspector,
  statusbar,
}: WorkbenchShellProps) {
  return (
    <div className="workbench">
      <header className="topbar">
        <div className="brand">{title}</div>
        <div className="crumb">{repoLabel}</div>
        <div className="topbarSpacer" />
        <div className="pill">{modelLabel}</div>
        <div className={`statusDot status-${status}`} />
      </header>
      <aside className="sidebar">{sidebar}</aside>
      <main className="editorPane">{editor}</main>
      <section className="inspector">{inspector}</section>
      <footer className="statusbar">{statusbar}</footer>
    </div>
  );
}
