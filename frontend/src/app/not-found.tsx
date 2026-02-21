import Link from "next/link";
import T from "@/components/ui/T";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <h1 className="text-6xl font-bold text-gray-300 mb-4"><T k="not_found.title" /></h1>
        <h2 className="text-xl font-semibold text-gray-900 mb-2"><T k="not_found.heading" /></h2>
        <p className="text-gray-600 mb-6"><T k="not_found.message" /></p>
        <div className="flex gap-3 justify-center">
          <Link
            href="/"
            className="px-6 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
          >
            <T k="not_found.go_home" />
          </Link>
          <Link
            href="/schemes"
            className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <T k="not_found.browse_schemes" />
          </Link>
        </div>
      </div>
    </div>
  );
}
