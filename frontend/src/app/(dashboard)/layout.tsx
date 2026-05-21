import Sidebar from "@/components/sidebar";
import Topbar from "@/components/topbar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <Topbar />
      <main className="ml-[240px] mt-14 p-8 bg-white min-h-[calc(100vh-56px)]">
        {children}
      </main>
    </div>
  );
}
