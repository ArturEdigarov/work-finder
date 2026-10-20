import { redirect } from "next/navigation";

// The profile page sends unauthenticated visitors to /login.
export default function Home() {
  redirect("/profile");
}
