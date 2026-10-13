// Numeric-only process telemetry. Loaded in both the runner and its test child.
// Never inspect game objects: their cyclic graph can dwarf the test itself.
process.on('exit',()=>{
  const {rss,heapUsed,external}=process.memoryUsage();
  process.stderr.write(`TEST_MEMORY ${JSON.stringify({pid:process.pid,rss,heapUsed,external,maxRSSKiB:process.resourceUsage().maxRSS})}\n`);
});
