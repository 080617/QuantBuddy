"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

export function WorkspaceCreatePlaceholder({ title }: { title: string }) {
  const router = useRouter();
  function goBack() {
    if (document.referrer && new URL(document.referrer).pathname.startsWith("/strategy")) router.back();
    else router.push("/strategy");
  }
  return <div className="ws-placeholder">
    <button type="button" onClick={goBack}><ArrowLeft />返回我的策略</button>
    <section><span>Workspace Phase 1A</span><h1>{title}</h1><p>下一阶段实现正式创建表单</p></section>
  </div>;
}
