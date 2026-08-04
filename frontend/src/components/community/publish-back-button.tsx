"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

export function PublishBackButton() {
  const router = useRouter();

  function goBack() {
    const referrer = document.referrer;
    if (referrer) {
      const previous = new URL(referrer);
      if (previous.origin === window.location.origin && previous.pathname.startsWith("/community")) {
        router.back();
        return;
      }
    }
    router.push("/community");
  }

  return <button type="button" className="qb-publish-back" aria-label="返回社区" onClick={goBack}><ArrowLeft aria-hidden="true" /></button>;
}
