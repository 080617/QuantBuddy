import { PageContainer } from "@/components/layout/page-container";

interface PhasePlaceholderProps {
  title: string;
}

export function PhasePlaceholder({ title }: PhasePlaceholderProps) {
  return (
    <PageContainer className="py-14 sm:py-20">
      <section className="rounded-3xl border border-line bg-white px-6 py-10 shadow-[0_18px_60px_rgba(21,32,51,0.06)] sm:px-10">
        <p className="text-sm font-semibold tracking-[0.16em] text-brand-600">
          QUANTBUDDY
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-ink-950 sm:text-4xl">
          {title}
        </h1>
        <p className="mt-4 text-base text-ink-700">
          该模块将在后续 Phase 完成。
        </p>
      </section>
    </PageContainer>
  );
}
