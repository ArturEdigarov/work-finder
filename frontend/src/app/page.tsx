import { redirect } from "next/navigation";

// The account page sends unauthenticated visitors to /login.
export default function Home() {
  redirect("/account");
}
