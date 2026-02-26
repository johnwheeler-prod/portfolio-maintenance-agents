import { Header } from "@/components/layout/header";
import { PipelineForm } from "@/components/run/pipeline-form";
import { RunStatus } from "@/components/run/run-status";

export default function RunPage() {
  return (
    <>
      <Header
        title="Run Pipelines"
        description="Trigger agent pipelines via GitHub Actions"
      />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div>
          <PipelineForm
            name="Site Audit"
            workflowFile="monthly-seo-audit.yml"
            fields={[
              { name: "mode", label: "Mode", type: "select", options: ["site", "page"], defaultValue: "site" },
              { name: "page_url", label: "Page URL (page mode)", type: "text" },
              { name: "sitemap_url", label: "Sitemap URL (site mode)", type: "text" },
              { name: "days", label: "GSC lookback days", type: "text", defaultValue: "28" },
              { name: "stale_months", label: "Stale months", type: "text", defaultValue: "3" },
              { name: "dry_run", label: "Dry run", type: "checkbox" },
            ]}
          />
          <RunStatus workflowFile="monthly-seo-audit.yml" />
        </div>

        <div>
          <PipelineForm
            name="Portfolio Audit"
            workflowFile="weekly-portfolio-audit.yml"
            fields={[
              { name: "portfolio_url", label: "Portfolio URL", type: "text" },
              { name: "dry_run", label: "Dry run", type: "checkbox" },
            ]}
          />
          <RunStatus workflowFile="weekly-portfolio-audit.yml" />
        </div>

        <div>
          <PipelineForm
            name="Content Pipeline"
            workflowFile="weekly-content-pipeline.yml"
            fields={[
              { name: "days", label: "GSC lookback days", type: "text", defaultValue: "28" },
              { name: "dry_run", label: "Dry run", type: "checkbox" },
            ]}
          />
          <RunStatus workflowFile="weekly-content-pipeline.yml" />
        </div>
      </div>
    </>
  );
}
