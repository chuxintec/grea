// Explicit existing-process AX binding and PID-directed input. Never launches apps.
#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>
#import <libproc.h>
#import <sys/stat.h>
#import <unistd.h>
#import <errno.h>
#import <math.h>

static NSDictionary *request;
static NSMutableDictionary *response;
static pid_t targetPid;
static NSUInteger posted;
static NSUInteger axActionsAttempted,axActionsPerformed;
static NSDictionary *preparedMousePoint,*preparedMouseBounds;
static CGPoint synchronizedPointer;
static NSDictionary *pointerSyncBounds;
static NSMutableDictionary *activeCursorSyncRecord;
static BOOL pointerSyncComplete;
static void Reject(NSString *code, NSString *message) {
    response[@"status"]=@"blocked";response[@"errorCode"]=code;response[@"message"]=message;
    @throw [NSException exceptionWithName:@"BindingBlocked" reason:message userInfo:nil];
}
static BOOL Integer(id v) { return [v isKindOfClass:[NSNumber class]] && CFGetTypeID((__bridge CFTypeRef)v)!=CFBooleanGetTypeID() && !CFNumberIsFloatType((__bridge CFNumberRef)v); }
static BOOL Nonnegative(id v) { return Integer(v) && ![[v stringValue] hasPrefix:@"-"]; }
static BOOL Number(id v) { return [v isKindOfClass:[NSNumber class]] && CFGetTypeID((__bridge CFTypeRef)v)!=CFBooleanGetTypeID() && isfinite([v doubleValue]); }
static void Identity(void) {
    struct proc_bsdinfo b={0};errno=0;
    int count=proc_pidinfo(targetPid,PROC_PIDTBSDINFO,0,&b,sizeof(b));
    if(count!=sizeof(b)) {
        if(kill(targetPid,0)==-1 && errno==ESRCH)Reject(@"PROCESS_NOT_FOUND",@"Selected process no longer exists");
        Reject(@"PROCESS_IDENTITY_UNAVAILABLE",@"Cannot read selected process identity");
    }
    if(b.pbi_uid!=getuid())Reject(@"PROCESS_UID_MISMATCH",@"Selected process belongs to a different user");
    NSArray *birth=request[@"startTime"];
    if(b.pbi_start_tvsec!=[birth[0] unsignedLongLongValue] || b.pbi_start_tvusec!=[birth[1] unsignedLongLongValue])Reject(@"PROCESS_BIRTH_MISMATCH",@"Selected process birth differs");
    char path[PROC_PIDPATHINFO_MAXSIZE]={0};
    if(proc_pidpath(targetPid,path,sizeof(path))<=0)Reject(@"PROCESS_EXECUTABLE_UNAVAILABLE",@"Cannot resolve selected executable");
    struct stat st;
    if(stat(path,&st)!=0 || !S_ISREG(st.st_mode))Reject(@"PROCESS_EXECUTABLE_UNAVAILABLE",@"Selected executable is unavailable");
    if((uint64_t)st.st_dev!=[request[@"executableDevice"] unsignedLongLongValue] || (uint64_t)st.st_ino!=[request[@"executableInode"] unsignedLongLongValue])Reject(@"PROCESS_EXECUTABLE_MISMATCH",@"Selected executable identity differs");
    // Bind bundle metadata to the kernel-resolved executable, never to a
    // LaunchServices cache entry which may conflate same-bundle instances.
    NSString *executable=[[NSString alloc] initWithUTF8String:path];
    NSString *macOS=executable.stringByDeletingLastPathComponent;
    NSString *contents=macOS.stringByDeletingLastPathComponent;
    NSString *bundle=contents.stringByDeletingLastPathComponent;
    if(![macOS.lastPathComponent isEqualToString:@"MacOS"]||![contents.lastPathComponent isEqualToString:@"Contents"]||![bundle.pathExtension.lowercaseString isEqualToString:@"app"])Reject(@"PROCESS_BUNDLE_UNAVAILABLE",@"Selected executable is not in an explicit app bundle");
    NSDictionary *metadata=[NSDictionary dictionaryWithContentsOfFile:[contents stringByAppendingPathComponent:@"Info.plist"]];
    NSString *bundleId=metadata[@"CFBundleIdentifier"];
    if(![bundleId isKindOfClass:[NSString class]]||![bundleId isEqualToString:request[@"bundleIdentifier"]])Reject(@"PROCESS_BUNDLE_MISMATCH",@"Executable-owned bundle identifier differs");
    NSString *bundleExecutable=metadata[@"CFBundleExecutable"];
    if(![bundleExecutable isKindOfClass:[NSString class]]||![bundleExecutable isEqualToString:executable.lastPathComponent])Reject(@"PROCESS_BUNDLE_EXECUTABLE_MISMATCH",@"Bundle executable declaration differs from kernel path");
    response[@"identity"]=@{@"pid":@(targetPid),@"startTime":@[@(b.pbi_start_tvsec),@(b.pbi_start_tvusec)],@"exeDevice":@((uint64_t)st.st_dev),@"exeInode":@((uint64_t)st.st_ino),@"bundleIdentifier":bundleId};
}
static NSArray *CGWindows(void) {
    NSArray *all=CFBridgingRelease(CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly|kCGWindowListExcludeDesktopElements,kCGNullWindowID));
    if(!all)Reject(@"WINDOW_ENUMERATION_UNAVAILABLE",@"Cannot enumerate visible windows");
    NSMutableArray *rows=[NSMutableArray array];
    for(NSDictionary *w in all) {
        if([w[(id)kCGWindowOwnerPID] intValue]!=targetPid || [w[(id)kCGWindowLayer] intValue]!=0)continue;
        CGRect bounds;
        if(!CGRectMakeWithDictionaryRepresentation((__bridge CFDictionaryRef)w[(id)kCGWindowBounds],&bounds) || !isfinite(bounds.origin.x)||!isfinite(bounds.origin.y)||!isfinite(bounds.size.width)||!isfinite(bounds.size.height)||bounds.size.width<=0 || bounds.size.height<=0)continue;
        NSMutableDictionary *r=[@{@"windowId":w[(id)kCGWindowNumber],@"ownerPid":@(targetPid),@"bounds":@{@"x":@(bounds.origin.x),@"y":@(bounds.origin.y),@"width":@(bounds.size.width),@"height":@(bounds.size.height)}} mutableCopy];
        NSString *title=w[(id)kCGWindowName];if([title isKindOfClass:[NSString class]] && title.length)r[@"title"]=title;
        [rows addObject:r];
    }
    return rows;
}
static BOOL AXMatches(AXUIElementRef win,NSDictionary *row) {
    pid_t pid=0;if(AXUIElementGetPid(win,&pid)!=kAXErrorSuccess||pid!=targetPid)return NO;
    CFTypeRef p=NULL,s=NULL;CGPoint position;CGSize size;
    AXError pe=AXUIElementCopyAttributeValue(win,kAXPositionAttribute,&p),se=AXUIElementCopyAttributeValue(win,kAXSizeAttribute,&s);
    BOOL ok=pe==kAXErrorSuccess&&se==kAXErrorSuccess&&p&&s&&CFGetTypeID(p)==AXValueGetTypeID()&&CFGetTypeID(s)==AXValueGetTypeID()&&AXValueGetValue((AXValueRef)p,kAXValueCGPointType,&position)&&AXValueGetValue((AXValueRef)s,kAXValueCGSizeType,&size);
    if(p)CFRelease(p);if(s)CFRelease(s);if(!ok||!isfinite(position.x)||!isfinite(position.y)||!isfinite(size.width)||!isfinite(size.height)||size.width<=0||size.height<=0)return NO;
    NSDictionary *b=row[@"bounds"];
    if(fabs(position.x-[b[@"x"] doubleValue])>1 || fabs(position.y-[b[@"y"] doubleValue])>1 || fabs(size.width-[b[@"width"] doubleValue])>1 || fabs(size.height-[b[@"height"] doubleValue])>1)return NO;
    if(row[@"title"]) { CFTypeRef title=NULL;AXError e=AXUIElementCopyAttributeValue(win,kAXTitleAttribute,&title);BOOL match=e==kAXErrorSuccess&&title&&CFGetTypeID(title)==CFStringGetTypeID()&&[(__bridge NSString *)title isEqual:row[@"title"]];if(title)CFRelease(title);if(!match)return NO; }
    return YES;
}
static AXUIElementRef Selected(AXUIElementRef app,BOOL requireFocus) {
    Identity();NSArray *cg=CGWindows();NSMutableArray *selected=[NSMutableArray array];
    for(NSDictionary *r in cg)if([r[@"windowId"] unsignedLongLongValue]==[request[@"windowId"] unsignedLongLongValue])[selected addObject:r];
    if(selected.count!=1)Reject(@"WINDOW_OWNER_MISMATCH",@"Selected visible window is absent or not uniquely owned");
    NSDictionary *row=selected[0];CFTypeRef list=NULL;
    if(AXUIElementCopyAttributeValue(app,kAXWindowsAttribute,&list)!=kAXErrorSuccess||!list||CFGetTypeID(list)!=CFArrayGetTypeID()){if(list)CFRelease(list);Reject(@"AX_WINDOWS_UNAVAILABLE",@"Cannot read selected process windows");}
    AXUIElementRef match=NULL;NSUInteger matches=0;
    for(id item in (__bridge NSArray *)list)if(CFGetTypeID((__bridge CFTypeRef)item)==AXUIElementGetTypeID()&&AXMatches((__bridge AXUIElementRef)item,row)){match=(__bridge AXUIElementRef)item;matches++;}
    if(matches!=1){CFRelease(list);Reject(@"WINDOW_MAPPING_AMBIGUOUS",@"CG and AX window mapping is not unique");}
    // A matching AX window must also map to exactly one CG window, not merely
    // the caller's preferred ID among overlapping identical windows.
    NSUInteger reverse=0;for(NSDictionary *other in cg)if(AXMatches(match,other))reverse++;
    if(reverse!=1){CFRelease(list);Reject(@"WINDOW_MAPPING_AMBIGUOUS",@"AX window maps to multiple visible CG windows");}
    CFRetain(match);CFRelease(list);
    if(requireFocus) {
        CFTypeRef focused=NULL;AXError e=AXUIElementCopyAttributeValue(app,kAXFocusedWindowAttribute,&focused);
        BOOL ok=e==kAXErrorSuccess&&focused&&CFGetTypeID(focused)==AXUIElementGetTypeID()&&CFEqual(match,focused);
        if(focused)CFRelease(focused);if(!ok){CFRelease(match);Reject(@"WINDOW_NOT_FOCUSED",@"Selected process focus is not the selected window");}
    }
    response[@"selectedWindow"]=row;return match;
}
static void Recheck(AXUIElementRef app) {AXUIElementRef w=Selected(app,YES);CFRelease(w);}
static CGPoint ReadPointer(void) {
    CGEventRef snapshot=CGEventCreate(NULL);if(!snapshot)Reject(@"CURSOR_STATE_UNAVAILABLE",@"Cannot read current pointer position");
    CGPoint p=CGEventGetLocation(snapshot);CFRelease(snapshot);
    if(!isfinite(p.x)||!isfinite(p.y))Reject(@"CURSOR_STATE_UNAVAILABLE",@"Current pointer position is not finite");
    return p;
}
static void GuardOwnedAXHit(AXUIElementRef app,CGPoint point,NSMutableDictionary *evidence) {
    AXUIElementRef selected=NULL,current=NULL,system=NULL;
    @try {
        selected=Selected(app,YES);system=AXUIElementCreateSystemWide();
        if(!system)Reject(@"CURSOR_AX_HIT_UNKNOWN",@"Cannot create a read-only system hit-test handle");
        AXError hit=AXUIElementCopyElementAtPosition(system,(float)point.x,(float)point.y,&current);
        evidence[@"hitError"]=@(hit);
        if(hit!=kAXErrorSuccess||!current)Reject(@"CURSOR_AX_HIT_UNKNOWN",@"Cannot identify the actual accessibility element at the target point");
        for(NSUInteger depth=0;depth<=12;depth++) {
            pid_t owner=0;AXError ownerError=AXUIElementGetPid(current,&owner);evidence[@"hitOwnerPid"]=@(owner);evidence[@"parentDepth"]=@(depth);
            if(ownerError!=kAXErrorSuccess||owner!=targetPid)Reject(@"CURSOR_AX_HIT_OWNER_MISMATCH",@"Actual hit element or ancestor is not owned by the selected process");
            if(CFEqual(current,selected)){evidence[@"windowMatch"]=@YES;evidence[@"matchMethod"]=depth==0?@"hit-is-selected-window":@"parent-is-selected-window";return;}
            CFTypeRef window=NULL;AXError windowError=AXUIElementCopyAttributeValue(current,kAXWindowAttribute,&window);
            if(windowError==kAXErrorSuccess&&window) {
                pid_t windowOwner=0;BOOL valid=CFGetTypeID(window)==AXUIElementGetTypeID()&&AXUIElementGetPid((AXUIElementRef)window,&windowOwner)==kAXErrorSuccess&&windowOwner==targetPid&&CFEqual(window,selected);
                CFRelease(window);if(!valid)Reject(@"CURSOR_AX_HIT_WINDOW_MISMATCH",@"Actual hit element names a different or unknown AX window");
                evidence[@"windowMatch"]=@YES;evidence[@"matchMethod"]=@"AXWindow-attribute-equals-selected";return;
            }
            if(window)CFRelease(window);
            if(windowError!=kAXErrorNoValue&&windowError!=kAXErrorAttributeUnsupported&&windowError!=kAXErrorSuccess)Reject(@"CURSOR_AX_HIT_UNKNOWN",@"Hit element window could not be read reliably");
            if(depth==12)Reject(@"CURSOR_AX_HIT_UNKNOWN",@"Hit ancestry did not prove the selected window within twelve parents");
            CFTypeRef parent=NULL;AXError parentError=AXUIElementCopyAttributeValue(current,kAXParentAttribute,&parent);
            if(parentError!=kAXErrorSuccess||!parent||CFGetTypeID(parent)!=AXUIElementGetTypeID()){if(parent)CFRelease(parent);Reject(@"CURSOR_AX_HIT_UNKNOWN",@"Hit element has no verifiable same-process window ancestor");}
            if(CFEqual(parent,current)){CFRelease(parent);Reject(@"CURSOR_AX_HIT_UNKNOWN",@"Cyclic hit ancestry cannot prove a window");}
            CFRelease(current);current=(AXUIElementRef)parent;
        }
    } @finally {if(system)CFRelease(system);if(current)CFRelease(current);if(selected)CFRelease(selected);}
}
static void GuardForegroundTopmost(AXUIElementRef app,CGPoint point,NSDictionary *expectedBounds) {
    Recheck(app);
    if(![response[@"selectedWindow"][@"bounds"] isEqual:expectedBounds])Reject(@"CURSOR_WINDOW_GEOMETRY_CHANGED",@"Selected window geometry changed during pointer synchronization");
    CFTypeRef front=NULL;AXError ax=AXUIElementCopyAttributeValue(app,kAXFrontmostAttribute,&front);
    BOOL active=ax==kAXErrorSuccess&&front&&CFGetTypeID(front)==CFBooleanGetTypeID()&&CFBooleanGetValue((CFBooleanRef)front);
    if(front)CFRelease(front);if(!active)Reject(@"CURSOR_TARGET_NOT_FRONTMOST",@"Pointer synchronization requires the selected app already frontmost");
    NSArray *windows=CFBridgingRelease(CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly|kCGWindowListExcludeDesktopElements,kCGNullWindowID));
    if(!windows)Reject(@"CURSOR_TOPMOST_UNPROVEN",@"Cannot inspect window stacking at target point");
    NSDictionary *topLayerZero=nil;NSUInteger selectedMatches=0,higherCount=0;NSMutableArray *higher=[NSMutableArray array];
    for(NSDictionary *w in windows) {
        CGRect bounds;if(!CGRectMakeWithDictionaryRepresentation((__bridge CFDictionaryRef)w[(id)kCGWindowBounds],&bounds)||!isfinite(bounds.origin.x)||!isfinite(bounds.origin.y)||!isfinite(bounds.size.width)||!isfinite(bounds.size.height))Reject(@"CURSOR_TOPMOST_UNPROVEN",@"Window bounds unavailable while checking stacking");
        if([w[(id)kCGWindowNumber] unsignedIntValue]==[request[@"windowId"] unsignedIntValue])selectedMatches++;
        if([w[(id)kCGWindowAlpha] doubleValue]>0&&CGRectContainsPoint(bounds,point)) {
            int layer=[w[(id)kCGWindowLayer] intValue];
            if(layer==0&&!topLayerZero)topLayerZero=w;
            if(layer>0){higherCount++;if(higher.count<16)[higher addObject:@{@"windowId":w[(id)kCGWindowNumber],@"ownerPid":w[(id)kCGWindowOwnerPID],@"layer":@(layer)}];}
        }
    }
    NSMutableDictionary *evidence=[NSMutableDictionary dictionaryWithDictionary:@{@"status":@"checking",@"point":@[@(point.x),@(point.y)],@"higherLayerRectanglesCoverPoint":@(higherCount>0),@"higherLayerRectangleCount":@(higherCount),@"higherLayerRectangles":higher,@"higherLayerListTruncated":@(higherCount>higher.count),@"windowMatch":@NO}];response[@"cursorHitEvidence"]=evidence;
    if(selectedMatches!=1||!topLayerZero||[topLayerZero[(id)kCGWindowOwnerPID] intValue]!=targetPid||[topLayerZero[(id)kCGWindowNumber] unsignedIntValue]!=[request[@"windowId"] unsignedIntValue])Reject(@"CURSOR_TOPMOST_UNPROVEN",@"First visible layer-zero window covering the point is not uniquely the selected window");
    evidence[@"topLayerZeroWindowId"]=topLayerZero[(id)kCGWindowNumber];
    GuardOwnedAXHit(app,point,evidence);
    Recheck(app);if(![response[@"selectedWindow"][@"bounds"] isEqual:expectedBounds])Reject(@"CURSOR_WINDOW_GEOMETRY_CHANGED",@"Selected window changed during hit verification");
    evidence[@"status"]=@"verified";
}
static void CheckSynchronizedPointer(AXUIElementRef app) {
    if(!pointerSyncComplete)return;
    GuardForegroundTopmost(app,synchronizedPointer,pointerSyncBounds);
    CGPoint current=ReadPointer();activeCursorSyncRecord[@"lastObserved"]=@[@(current.x),@(current.y)];
    if(fabs(current.x-synchronizedPointer.x)>0.5||fabs(current.y-synchronizedPointer.y)>0.5)Reject(@"CURSOR_MOVED_AFTER_SYNC",@"Pointer changed after synchronization; no further input or restoration attempted");
}
static void SynchronizePointer(AXUIElementRef app,NSDictionary *point) {
    if(![request[@"cursorMode"] isEqual:@"sync-owned-window"])Reject(@"CURSOR_MODE_REQUIRED",@"Pointer synchronization requires explicit sync-owned-window mode");
    NSMutableArray *history=response[@"cursorSyncHistory"];if(!history){history=[NSMutableArray array];response[@"cursorSyncHistory"]=history;}
    NSMutableDictionary *record=[NSMutableDictionary dictionaryWithDictionary:@{@"mode":@"sync-owned-window",@"pointIndex":@(history.count),@"relativePoint":[point copy],@"attempted":@NO,@"completed":@NO,@"restoreAttempted":@NO,@"before":[NSNull null],@"after":[NSNull null],@"target":[NSNull null],@"eventsPostedBeforeSync":@(posted),@"phase":@"checking-previous-pointer",@"limitation":@"physical pointer side effect; layer-zero plus exact AX hit checked; non-atomic; never restored to another position"}];
    [history addObject:record];response[@"cursorSync"]=record;
    // Do not hide a human/engine pointer change by synchronizing the next point.
    CheckSynchronizedPointer(app);
    pointerSyncComplete=NO;activeCursorSyncRecord=record;record[@"phase"]=@"checking-target";
    Recheck(app);pointerSyncBounds=[response[@"selectedWindow"][@"bounds"] copy];
    double x=[point[@"x"] doubleValue],y=[point[@"y"] doubleValue];
    if(x<0||y<0||x>=[pointerSyncBounds[@"width"] doubleValue]||y>=[pointerSyncBounds[@"height"] doubleValue])Reject(@"POINT_OUTSIDE_WINDOW",@"Pointer sync point outside selected window");
    synchronizedPointer=CGPointMake([pointerSyncBounds[@"x"] doubleValue]+x,[pointerSyncBounds[@"y"] doubleValue]+y);
    record[@"target"]=@[@(synchronizedPointer.x),@(synchronizedPointer.y)];
    GuardForegroundTopmost(app,synchronizedPointer,pointerSyncBounds);record[@"hitBefore"]=response[@"cursorHitEvidence"];
    CGPoint before=ReadPointer();record[@"before"]=@[@(before.x),@(before.y)];
    GuardForegroundTopmost(app,synchronizedPointer,pointerSyncBounds);record[@"hitBefore"]=response[@"cursorHitEvidence"];
    record[@"attempted"]=@YES;record[@"phase"]=@"synchronizing";
    CGError result=CGWarpMouseCursorPosition(synchronizedPointer);record[@"resultCode"]=@(result);record[@"apiSucceeded"]=@(result==kCGErrorSuccess);
    usleep(120000);
    CGPoint after=ReadPointer();record[@"after"]=@[@(after.x),@(after.y)];record[@"phase"]=@"checking-after";
    if(result!=kCGErrorSuccess)Reject(@"CURSOR_SYNC_FAILED",@"Pointer synchronization API failed; inspect recorded pointer side effects");
    GuardForegroundTopmost(app,synchronizedPointer,pointerSyncBounds);record[@"hitAfter"]=response[@"cursorHitEvidence"];
    if(fabs(after.x-synchronizedPointer.x)>0.5||fabs(after.y-synchronizedPointer.y)>0.5)Reject(@"CURSOR_SYNC_UNPROVEN",@"Pointer did not remain at requested point after wait");
    pointerSyncComplete=YES;record[@"completed"]=@YES;record[@"phase"]=@"synchronized";
}
static void RouteMouse(CGEventRef event,CGWindowID windowId) {
    CGEventType type=CGEventGetType(event);
    BOOL right=type==kCGEventRightMouseDown||type==kCGEventRightMouseUp||type==kCGEventRightMouseDragged;
    BOOL up=type==kCGEventLeftMouseUp||type==kCGEventRightMouseUp;
    // PID-directed posting bypasses the normal global window-server routing
    // path. Supply both public window annotations explicitly after rechecking.
    CGEventSetIntegerValueField(event,kCGMouseEventWindowUnderMousePointer,windowId);
    CGEventSetIntegerValueField(event,kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent,windowId);
    CGEventSetIntegerValueField(event,kCGMouseEventClickState,type==kCGEventMouseMoved?0:1);
    CGEventSetIntegerValueField(event,kCGMouseEventButtonNumber,right?kCGMouseButtonRight:kCGMouseButtonLeft);
    CGEventSetIntegerValueField(event,kCGMouseEventNumber,1); // same down/drag/up gesture
    CGEventSetDoubleValueField(event,kCGMouseEventPressure,(up||type==kCGEventMouseMoved)?0.0:1.0);
    CGEventSetFlags(event,0);
}
static void Post(AXUIElementRef app,CGEventRef event) {
    if(!event)Reject(@"EVENT_CREATION_FAILED",@"Cannot create targeted input event");
    @try {Recheck(app);CheckSynchronizedPointer(app);
        CGEventType type=CGEventGetType(event);
        if(type==kCGEventMouseMoved||type==kCGEventLeftMouseDown||type==kCGEventLeftMouseUp||type==kCGEventLeftMouseDragged||type==kCGEventRightMouseDown||type==kCGEventRightMouseUp||type==kCGEventRightMouseDragged) {
            NSDictionary *b=response[@"selectedWindow"][@"bounds"];
            if(![b isEqual:preparedMouseBounds])Reject(@"WINDOW_MOVED_BEFORE_EVENT",@"Selected window geometry changed after event preparation");
            NSEvent *native=[NSEvent eventWithCGEvent:event];CGPoint payload=CGEventGetLocation(event);
            double expectedX=[preparedMousePoint[@"x"] doubleValue],expectedY=[preparedMousePoint[@"y"] doubleValue];
            if(!native||native.windowNumber!=[request[@"windowId"] integerValue]||!isfinite(payload.x)||!isfinite(payload.y)||payload.x<0||payload.y<0||payload.x>=[b[@"width"] doubleValue]||payload.y>=[b[@"height"] doubleValue]||fabs(payload.x-expectedX)>0.001||fabs(payload.y-expectedY)>0.001)Reject(@"EVENT_WINDOW_COORDINATE_MISMATCH",@"Measured window-relative payload or explicit window annotation differs");
            RouteMouse(event,[response[@"selectedWindow"][@"windowId"] unsignedIntValue]);
            response[@"mouseRouting"]=@"explicit-selected-window-id-public-fields-91-92";
        }
        CGEventPostToPid(targetPid,event);posted++;} @finally {CFRelease(event);}
    usleep(50000);
}
static CGPoint RelativePoint(NSDictionary *relative) {
    NSDictionary *b=response[@"selectedWindow"][@"bounds"];
    double x=[relative[@"x"] doubleValue],y=[relative[@"y"] doubleValue];
    if(x<0||y<0||x>=[b[@"width"] doubleValue]||y>=[b[@"height"] doubleValue])Reject(@"POINT_OUTSIDE_WINDOW",@"Input point lies outside selected window bounds");
    return CGPointMake([b[@"x"] doubleValue]+x,[b[@"y"] doubleValue]+y);
}
static CGEventRef WindowMouseEvent(NSEventType type,NSDictionary *point) {
    RelativePoint(point);NSDictionary *row=response[@"selectedWindow"],*bounds=row[@"bounds"];
    preparedMousePoint=[point copy];preparedMouseBounds=[bounds copy];
    // PID-directed AppKit dispatch consumes a window-relative payload.
    // Measure the public NSEvent conversion in this host coordinate space;
    // never mutate its CG location/cache or guess a display-height offset.
    CGPoint desired=CGPointMake([point[@"x"] doubleValue],[point[@"y"] doubleValue]);
    NSPoint encoded=NSMakePoint(desired.x,[bounds[@"height"] doubleValue]-desired.y);
    BOOL up=type==NSEventTypeLeftMouseUp||type==NSEventTypeRightMouseUp;
    CGEventRef result=NULL;NSUInteger attempts=0;
    for(NSUInteger i=0;i<2;i++) {
        attempts=i+1;
        NSEvent *native=[NSEvent mouseEventWithType:type location:encoded modifierFlags:0 timestamp:NSProcessInfo.processInfo.systemUptime windowNumber:[row[@"windowId"] integerValue] context:nil eventNumber:1 clickCount:type==NSEventTypeMouseMoved?0:1 pressure:(up||type==NSEventTypeMouseMoved)?0.0:1.0];
        if(!native||!native.CGEvent||native.windowNumber!=[row[@"windowId"] integerValue])Reject(@"EVENT_CREATION_FAILED",@"Measured-coordinate event creation failed");
        CGEventRef event=CGEventCreateCopy(native.CGEvent);if(!event)Reject(@"EVENT_CREATION_FAILED",@"Cannot copy window-bound event");
        CGPoint observed=CGEventGetLocation(event);
        if(!isfinite(observed.x)||!isfinite(observed.y)){CFRelease(event);Reject(@"EVENT_WINDOW_COORDINATE_MISMATCH",@"Nonfinite measured conversion");}
        if(fabs(observed.x-desired.x)<0.001&&fabs(observed.y-desired.y)<0.001){result=event;break;}
        CFRelease(event);encoded.x+=desired.x-observed.x;encoded.y+=observed.y-desired.y;
    }
    if(!result)Reject(@"EVENT_WINDOW_COORDINATE_MISMATCH",@"Measured conversion did not converge within two constructions");
    NSEvent *roundtrip=[NSEvent eventWithCGEvent:result];CGPoint payload=CGEventGetLocation(result);
    if(!roundtrip||roundtrip.windowNumber!=[row[@"windowId"] integerValue]){CFRelease(result);Reject(@"EVENT_WINDOW_COORDINATE_MISMATCH",@"Window-bound event lost explicit window annotation");}
    response[@"coordinateEncoding"]=@"NSEvent-measured-public-conversion-window-relative-payload";
    response[@"encodedNSPoint"]=@[@(encoded.x),@(encoded.y)];response[@"mousePayload"]=@[@(payload.x),@(payload.y)];response[@"roundtripNSPoint"]=@[@(roundtrip.locationInWindow.x),@(roundtrip.locationInWindow.y)];response[@"constructionAttempts"]=@(attempts);
    return result;
}
static void CloseWindow(AXUIElementRef app,AXUIElementRef window) {
    CFTypeRef button=NULL;
    if(AXUIElementCopyAttributeValue(window,kAXCloseButtonAttribute,&button)!=kAXErrorSuccess||!button||CFGetTypeID(button)!=AXUIElementGetTypeID()) {if(button)CFRelease(button);Reject(@"AX_CLOSE_UNAVAILABLE",@"Selected window has no accessible close button");}
    @try {
        pid_t owner=0;if(AXUIElementGetPid((AXUIElementRef)button,&owner)!=kAXErrorSuccess||owner!=targetPid)Reject(@"AX_CLOSE_OWNER_MISMATCH",@"Close button is not owned by selected process");
        Recheck(app);Identity();axActionsAttempted++;
        AXError result=AXUIElementPerformAction((AXUIElementRef)button,kAXPressAction);
        if(result!=kAXErrorSuccess)Reject(@"AX_CLOSE_FAILED",@"Close-button action did not report success; inspect selected process");
        axActionsPerformed++;usleep(50000);Identity();
        BOOL stillVisible=NO;for(NSDictionary *row in CGWindows())if([row[@"windowId"] unsignedLongLongValue]==[request[@"windowId"] unsignedLongLongValue])stillVisible=YES;
        response[@"windowCloseObserved"]=@(!stillVisible);response[@"status"]=@"performed";
        if(stillVisible)Recheck(app);
    } @finally {CFRelease(button);}
}
static NSString *BoundedString(CFTypeRef value) {
    if(!value||CFGetTypeID(value)!=CFStringGetTypeID())return nil;
    NSString *s=(__bridge NSString *)value;return s.length<=256?s:[s substringToIndex:256];
}
static NSDictionary *Snapshot(AXUIElementRef root) {
    NSMutableArray *queue=[NSMutableArray arrayWithObject:@{@"element":(__bridge id)root,@"depth":@0}],*nodes=[NSMutableArray array];
    BOOL partial=NO,truncated=NO;CFAbsoluteTime deadline=CFAbsoluteTimeGetCurrent()+5.0;
    for(NSUInteger cursor=0;cursor<queue.count;cursor++) {
        if(nodes.count>=128||CFAbsoluteTimeGetCurrent()>deadline){partial=YES;truncated=YES;break;}
        NSDictionary *entry=queue[cursor];AXUIElementRef element=(__bridge AXUIElementRef)entry[@"element"];pid_t owner=0;
        if(AXUIElementGetPid(element,&owner)!=kAXErrorSuccess||owner!=targetPid){partial=YES;continue;}
        AXUIElementSetMessagingTimeout(element,0.2);NSUInteger depth=[entry[@"depth"] unsignedIntegerValue];
        NSMutableDictionary *row=[NSMutableDictionary dictionaryWithDictionary:@{@"index":@(nodes.count),@"depth":@(depth)}];
        CFTypeRef role=NULL,title=NULL,value=NULL;
        if(AXUIElementCopyAttributeValue(element,kAXRoleAttribute,&role)!=kAXErrorSuccess)partial=YES;
        NSString *roleText=BoundedString(role);row[@"role"]=roleText?:@"unknown";
        AXUIElementCopyAttributeValue(element,kAXTitleAttribute,&title);NSString *titleText=BoundedString(title);if(titleText)row[@"title"]=titleText;
        // Only static labels expose value. Secure and editable fields never do.
        if([roleText isEqualToString:(__bridge NSString *)kAXStaticTextRole]){AXUIElementCopyAttributeValue(element,kAXValueAttribute,&value);NSString *v=BoundedString(value);if(v)row[@"value"]=v;}
        if(role)CFRelease(role);if(title)CFRelease(title);if(value)CFRelease(value);
        CFTypeRef position=NULL,size=NULL;CGPoint pt;CGSize sz;
        AXUIElementCopyAttributeValue(element,kAXPositionAttribute,&position);AXUIElementCopyAttributeValue(element,kAXSizeAttribute,&size);
        if(position&&size&&CFGetTypeID(position)==AXValueGetTypeID()&&CFGetTypeID(size)==AXValueGetTypeID()&&AXValueGetValue((AXValueRef)position,kAXValueCGPointType,&pt)&&AXValueGetValue((AXValueRef)size,kAXValueCGSizeType,&sz)&&isfinite(pt.x)&&isfinite(pt.y)&&isfinite(sz.width)&&isfinite(sz.height)&&sz.width>=0&&sz.height>=0) {
            NSDictionary *b=response[@"selectedWindow"][@"bounds"];row[@"bounds"]=@{@"x":@(pt.x-[b[@"x"] doubleValue]),@"y":@(pt.y-[b[@"y"] doubleValue]),@"width":@(sz.width),@"height":@(sz.height)};
        }
        if(position)CFRelease(position);if(size)CFRelease(size);[nodes addObject:row];
        CFTypeRef children=NULL;AXError error=AXUIElementCopyAttributeValue(element,kAXChildrenAttribute,&children);
        if(error!=kAXErrorSuccess&&error!=kAXErrorNoValue&&error!=kAXErrorAttributeUnsupported)partial=YES;
        if(children&&CFGetTypeID(children)==CFArrayGetTypeID()) {
            for(id child in (__bridge NSArray *)children) {
                if(depth>=8||queue.count>=128){truncated=YES;partial=YES;break;}
                if(CFGetTypeID((__bridge CFTypeRef)child)!=AXUIElementGetTypeID()){partial=YES;continue;}
                BOOL visited=NO;for(NSDictionary *prior in queue)if(CFEqual((__bridge CFTypeRef)prior[@"element"],(__bridge CFTypeRef)child)){visited=YES;break;}
                if(!visited)[queue addObject:@{@"element":child,@"depth":@(depth+1)}];
            }
        }
        if(children)CFRelease(children);
    }
    return @{@"status":partial?@"partial":@"complete",@"truncated":@(truncated),@"nodes":nodes};
}
static void Validate(void) {
    if(![request isKindOfClass:[NSDictionary class]])Reject(@"INVALID_REQUEST",@"Expected JSON object");
    NSString *op=request[@"operation"];NSSet *ops=[NSSet setWithArray:@[@"windows",@"observe",@"click",@"drag",@"key",@"text",@"close"]];
    if(![op isKindOfClass:[NSString class]]||![ops containsObject:op])Reject(@"INVALID_OPERATION",@"Unknown operation");
    NSMutableSet *allowed=[NSMutableSet setWithArray:@[@"operation",@"pid",@"startTime",@"executableDevice",@"executableInode",@"bundleIdentifier"]];
    if(![op isEqual:@"windows"])[allowed addObject:@"windowId"];
    if([op isEqual:@"click"])[allowed addObjectsFromArray:@[@"x",@"y",@"button",@"cursorMode"]];
    if([op isEqual:@"drag"])[allowed addObjectsFromArray:@[@"points",@"button",@"cursorMode"]];
    if([op isEqual:@"key"])[allowed addObject:@"key"];
    if([op isEqual:@"text"])[allowed addObject:@"text"];
    for(id k in request)if(![allowed containsObject:k])Reject(@"INVALID_REQUEST",@"Unknown request field");
    if(request[@"cursorMode"]&&![request[@"cursorMode"] isEqual:@"sync-owned-window"])Reject(@"INVALID_CURSOR_MODE",@"Only explicit sync-owned-window mode is supported for click or drag");
    if(!Integer(request[@"pid"])||[request[@"pid"] longLongValue]<=0||[request[@"pid"] unsignedLongLongValue]>INT_MAX)Reject(@"INVALID_REQUEST",@"Expected positive pid");
    targetPid=[request[@"pid"] intValue];NSArray *birth=request[@"startTime"];
    if(![birth isKindOfClass:[NSArray class]]||birth.count!=2||!Nonnegative(birth[0])||!Nonnegative(birth[1])||[birth[0] unsignedLongLongValue]==0||[birth[1] unsignedLongLongValue]>=1000000)Reject(@"INVALID_REQUEST",@"Expected exact process start time");
    if(!Nonnegative(request[@"executableDevice"])||!Nonnegative(request[@"executableInode"])||[request[@"executableInode"] unsignedLongLongValue]==0)Reject(@"INVALID_REQUEST",@"Expected executable device/inode integers");
    if(![request[@"bundleIdentifier"] isKindOfClass:[NSString class]]||[request[@"bundleIdentifier"] length]==0||[request[@"bundleIdentifier"] length]>256)Reject(@"INVALID_REQUEST",@"Expected bounded bundle identifier");
    if(![op isEqual:@"windows"]&&(!Nonnegative(request[@"windowId"])||[request[@"windowId"] unsignedLongLongValue]==0||[request[@"windowId"] unsignedLongLongValue]>UINT32_MAX))Reject(@"INVALID_REQUEST",@"Expected explicit window ID");
    if(request[@"button"]&&![@[@"left",@"right"] containsObject:request[@"button"]])Reject(@"INVALID_REQUEST",@"Unsupported mouse button");
    if([op isEqual:@"click"]&&(!Number(request[@"x"])||!Number(request[@"y"])))Reject(@"INVALID_REQUEST",@"Expected finite point coordinates");
    if([op isEqual:@"drag"]) {
        NSArray *points=request[@"points"];if(![points isKindOfClass:[NSArray class]]||points.count<2||points.count>64)Reject(@"INVALID_REQUEST",@"Drag requires 2..64 bounded points");
        for(id p in points)if(![p isKindOfClass:[NSDictionary class]]||[p count]!=2||!Number(p[@"x"])||!Number(p[@"y"]))Reject(@"INVALID_REQUEST",@"Expected exact finite drag points");
    }
    if([op isEqual:@"key"]&&![@[@"return",@"escape",@"space",@"tab",@"left",@"right",@"up",@"down",@"backspace",@"command-q"] containsObject:request[@"key"]?:[NSNull null]])Reject(@"INVALID_REQUEST",@"Unsupported key");
    if([op isEqual:@"text"]&&(![request[@"text"] isKindOfClass:[NSString class]]||[request[@"text"] length]==0||[request[@"text"] length]>256))Reject(@"INVALID_REQUEST",@"Text requires 1..256 UTF-16 code units");
}
int main(void) {@autoreleasepool {
    response=[NSMutableDictionary dictionaryWithDictionary:@{@"status":@"blocked",@"eventsPosted":@0,@"inputDelivery":@"not-posted",@"identityGuarantee":@"checked-before-each-event-and-after; not atomic against process/window replacement",@"coordinateSpace":@"window-bounds-relative-including-titlebar"}];
    AXUIElementRef app=NULL;
    @try {
        NSMutableData *data=[NSMutableData data];unsigned char buffer[4096];size_t n;
        while((n=fread(buffer,1,sizeof(buffer),stdin))>0){if(data.length+n>65536)Reject(@"REQUEST_TOO_LARGE",@"Request exceeds 65536 bytes");[data appendBytes:buffer length:n];}
        NSError *error=nil;request=[NSJSONSerialization JSONObjectWithData:data options:0 error:&error];if(error)Reject(@"INVALID_JSON",@"Invalid JSON request");Validate();
        if(!AXIsProcessTrusted())Reject(@"AX_PERMISSION_REQUIRED",@"Existing Accessibility permission is required");
        Identity();app=AXUIElementCreateApplication(targetPid);if(!app)Reject(@"AX_APPLICATION_UNAVAILABLE",@"Cannot bind existing AX application");
        AXUIElementSetMessagingTimeout(app,2.0);
        NSString *op=request[@"operation"];
        if([op isEqual:@"windows"]) {
            NSArray *rows=CGWindows();if(rows.count==0)Reject(@"WINDOW_NOT_FOUND",@"Selected process has no visible layer-zero window");NSMutableArray *bound=[NSMutableArray array];
            for(NSDictionary *row in rows) {NSDictionary *saved=request;NSMutableDictionary *probe=[request mutableCopy];probe[@"windowId"]=row[@"windowId"];request=probe;
                @try {AXUIElementRef w=Selected(app,NO);CFRelease(w);[bound addObject:row];} @finally {request=saved;}
            }
            response[@"windows"]=bound;Identity();response[@"status"]=@"verified";
        } else {
            AXUIElementRef w=Selected(app,[op isEqual:@"observe"]);
            if([op isEqual:@"observe"]){response[@"axSnapshot"]=Snapshot(w);CFRelease(w);Recheck(app);response[@"status"]=@"verified";}
            else if([op isEqual:@"close"]){@try {CloseWindow(app,w);} @finally {CFRelease(w);}}
            else {
                if(!CGPreflightPostEventAccess()){CFRelease(w);Reject(@"INPUT_PERMISSION_REQUIRED",@"Existing event-post permission is required");}
                Identity();AXUIElementSetAttributeValue(app,kAXFrontmostAttribute,kCFBooleanTrue);
                Identity();AXError raised=AXUIElementPerformAction(w,kAXRaiseAction);if(raised!=kAXErrorSuccess){CFRelease(w);Reject(@"WINDOW_RAISE_FAILED",@"Cannot raise the selected window");}
                Identity();AXUIElementSetAttributeValue(app,kAXFocusedWindowAttribute,w);CFRelease(w);usleep(20000);Recheck(app);
                CGEventSourceRef source=CGEventSourceCreate(kCGEventSourceStatePrivate);
                if(!source)Reject(@"EVENT_CREATION_FAILED",@"Cannot create private event source");
                @try {
                    if([op isEqual:@"click"]||[op isEqual:@"drag"]) {
                        BOOL right=[request[@"button"] isEqual:@"right"];
                        NSArray *points=[op isEqual:@"click"]?@[@{@"x":request[@"x"],@"y":request[@"y"]}]:request[@"points"];
                        for(NSDictionary *p in points)RelativePoint(p); // Validate whole gesture before its first event.
                        if(request[@"cursorMode"]) {
                            SynchronizePointer(app,points[0]);
                            // InputSystem receives button state without position unless
                            // the guarded initial move is sent before the first down.
                            Recheck(app);Post(app,WindowMouseEvent(NSEventTypeMouseMoved,points[0]));
                        }
                        Recheck(app);Post(app,WindowMouseEvent(right?NSEventTypeRightMouseDown:NSEventTypeLeftMouseDown,points[0]));
                        for(NSUInteger i=1;i<points.count;i++){Recheck(app);if(request[@"cursorMode"])SynchronizePointer(app,points[i]);Post(app,WindowMouseEvent(right?NSEventTypeRightMouseDragged:NSEventTypeLeftMouseDragged,points[i]));}
                        Recheck(app);Post(app,WindowMouseEvent(right?NSEventTypeRightMouseUp:NSEventTypeLeftMouseUp,points.lastObject));
                    } else {
                        NSDictionary *keys=@{@"return":@36,@"escape":@53,@"space":@49,@"tab":@48,@"left":@123,@"right":@124,@"up":@126,@"down":@125,@"backspace":@51,@"command-q":@12};
                        for(int down=1;down>=0;down--){CGEventRef event=CGEventCreateKeyboardEvent(source,[keys[request[@"key"]?:@""] unsignedShortValue],down);
                            if(event&&[op isEqual:@"text"]){NSString *t=request[@"text"];UniChar text[256];[t getCharacters:text range:NSMakeRange(0,t.length)];CGEventKeyboardSetUnicodeString(event,t.length,text);}
                            if(event&&[request[@"key"] isEqual:@"command-q"])CGEventSetFlags(event,kCGEventFlagMaskCommand);
                            Post(app,event);
                        }
                    }
                } @finally {if(source)CFRelease(source);}
                Recheck(app);CheckSynchronizedPointer(app);response[@"status"]=@"performed";
            }
        }
    } @catch(NSException *e) {
        if(![e.name isEqual:@"BindingBlocked"]){response[@"status"]=@"blocked";response[@"errorCode"]=@"NATIVE_BINDING_FAILED";response[@"message"]=@"Native binding operation failed";}
        if(((posted>0&&[request[@"key"] isEqual:@"command-q"])||axActionsPerformed>0)&&[response[@"errorCode"] isEqual:@"PROCESS_NOT_FOUND"]){response[@"status"]=@"performed_exit_observed";response[@"exitObserved"]=@YES;}
    } @finally {if(app)CFRelease(app);}
    NSUInteger syncAttempted=0,syncCompleted=0;for(NSDictionary *entry in response[@"cursorSyncHistory"]){if([entry[@"attempted"] boolValue])syncAttempted++;if([entry[@"completed"] boolValue])syncCompleted++;}
    response[@"cursorSyncAttemptedCount"]=@(syncAttempted);response[@"cursorSyncCompletedCount"]=@(syncCompleted);response[@"cursorPositionMayHaveChanged"]=@(syncAttempted>0);response[@"cursorRestorationAttempted"]=@NO;
    if([response[@"status"] isEqual:@"blocked"]&&(posted>0||axActionsAttempted>0||syncAttempted>0))response[@"partialEffects"]=@YES;
    response[@"eventsPosted"]=@(posted);response[@"axActionsAttempted"]=@(axActionsAttempted);response[@"axActionsPerformed"]=@(axActionsPerformed);if(axActionsAttempted)response[@"inputDelivery"]=@"ax-close-button-action-not-business-acceptance";if(posted)response[@"inputDelivery"]=@"posted-to-pid-not-business-acceptance";
    NSData *result=[NSJSONSerialization dataWithJSONObject:response options:NSJSONWritingSortedKeys error:nil];fwrite(result.bytes,1,result.length,stdout);fputc('\n',stdout);
    return [response[@"status"] isEqual:@"blocked"]?3:0;
}}
