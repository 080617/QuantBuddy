interface AppPlaceholderProps {
  title: string;
}

export function AppPlaceholder({ title }: AppPlaceholderProps) {
  return (
    <div className="qb-app-placeholder">
      <h1>{title}</h1>
      <p>功能开发中</p>
    </div>
  );
}
