// The release this build belongs to. The release workflow builds the web app after tagging the
// merge and passes the tag and commit in; a local build has neither.
const version = import.meta.env.VITE_APP_VERSION as string | undefined;
const commit = import.meta.env.VITE_APP_COMMIT as string | undefined;

export const releaseLabel = version
  ? `v${version}${commit ? ` · ${commit.slice(0, 7)}` : ""}`
  : "dev build";
