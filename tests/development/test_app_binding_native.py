"""Compile the native bridge and exercise only rejection paths, never UI input."""
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[2]/'src/grea/development/targets/BeaverAppBinding.m'

@unittest.skipUnless(platform.system()=='Darwin','macOS AX bridge')
class AppBindingNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=SOURCE.parents[3]/'.private/app-binding-native/tests'
        root.mkdir(parents=True,exist_ok=True)
        cls.directory=tempfile.TemporaryDirectory(dir=root);cls.root=Path(cls.directory.name)
        cls.binary=cls.root/'bridge';cls.denied=cls.root/'denied';cls.routing=cls.root/'routing';cls.no_mode=cls.root/'no-mode';cls.sequence=cls.root/'sequence'
        cls.flags=['xcrun','clang','-fobjc-arc','-Wall','-Wextra','-Werror','-framework','Foundation','-framework','AppKit','-framework','ApplicationServices']
        subprocess.run(cls.flags+[str(SOURCE),'-o',str(cls.binary)],check=True,capture_output=True)
        shim=cls.root/'denied.m'
        shim.write_text('#import <Foundation/Foundation.h>\n#import <AppKit/AppKit.h>\n#import <ApplicationServices/ApplicationServices.h>\nstatic Boolean TestAXIsProcessTrusted(void){return false;}\n#define AXIsProcessTrusted TestAXIsProcessTrusted\n#include "'+str(SOURCE)+'"\n')
        subprocess.run(cls.flags+[str(shim),'-o',str(cls.denied)],check=True,capture_output=True)
        routing=cls.root/'routing.m'
        routing.write_text('#define main BeaverBindingMain\n#include "'+str(SOURCE)+'"\n#undef main\n'+r'''int main(void){@autoreleasepool {
            BOOL ok=YES;NSUInteger checked=0;
            NSArray *geometries=@[@{@"x":@140,@"y":@470,@"width":@480,@"height":@332},@{@"x":@(-1920),@"y":@0,@"width":@1024,@"height":@768},@{@"x":@0,@"y":@(-200),@"width":@640,@"height":@1000}];
            NSArray *types=@[@(NSEventTypeMouseMoved),@(NSEventTypeLeftMouseDown),@(NSEventTypeLeftMouseUp),@(NSEventTypeLeftMouseDragged),@(NSEventTypeRightMouseDown),@(NSEventTypeRightMouseUp),@(NSEventTypeRightMouseDragged)];
            for(NSDictionary *bounds in geometries) {
                NSArray *points=@[@{@"x":@0,@"y":@0},@{@"x":@190.25,@"y":@183.5},@{@"x":@([bounds[@"width"] doubleValue]-.5),@"y":@([bounds[@"height"] doubleValue]-.5)}];
                for(NSDictionary *point in points)for(NSNumber *type in types){
                    response=[NSMutableDictionary dictionaryWithDictionary:@{@"selectedWindow":@{@"windowId":@12345,@"bounds":bounds}}];
                    CGEventRef event=WindowMouseEvent([type unsignedIntegerValue],point);RouteMouse(event,12345);
                    NSEvent *roundtrip=[NSEvent eventWithCGEvent:event];CGPoint at=CGEventGetLocation(event);
                    ok=ok&&roundtrip.windowNumber==12345&&fabs(at.x-[point[@"x"] doubleValue])<.001&&fabs(at.y-[point[@"y"] doubleValue])<.001&&[response[@"constructionAttempts"] unsignedIntegerValue]<=2&&CGEventGetIntegerValueField(event,kCGMouseEventWindowUnderMousePointer)==12345&&CGEventGetIntegerValueField(event,kCGMouseEventWindowUnderMousePointerThatCanHandleThisEvent)==12345&&CGEventGetIntegerValueField(event,kCGMouseEventClickState)==([type unsignedIntegerValue]==NSEventTypeMouseMoved?0:1)&&CGEventGetDoubleValueField(event,kCGMouseEventPressure)==(([type unsignedIntegerValue]==NSEventTypeMouseMoved||[type unsignedIntegerValue]==NSEventTypeLeftMouseUp||[type unsignedIntegerValue]==NSEventTypeRightMouseUp)?0.0:1.0)&&CGEventGetIntegerValueField(event,kCGMouseEventNumber)==1;
                    CFRelease(event);checked++;
                }
            }
            BOOL outside=NO;@try {WindowMouseEvent(NSEventTypeLeftMouseDown,@{@"x":@(-1),@"y":@0});} @catch(NSException *e){outside=[response[@"errorCode"] isEqual:@"POINT_OUTSIDE_WINDOW"];}
            CGRect display=CGDisplayBounds(CGMainDisplayID());NSDictionary *receipt=@{@"cases":@(checked),@"eventsPosted":@(posted),@"outsideRefused":@(outside),@"displayBounds":@[@(display.origin.x),@(display.origin.y),@(display.size.width),@(display.size.height)],@"passed":@(ok&&outside&&posted==0)};
            NSData *out=[NSJSONSerialization dataWithJSONObject:receipt options:0 error:nil];fwrite(out.bytes,1,out.length,stdout);
            return ok&&outside&&posted==0?0:1;
        }}''')
        subprocess.run(cls.flags+[str(routing),'-o',str(cls.routing)],check=True,capture_output=True)
        no_mode=cls.root/'no-mode.m'
        no_mode.write_text('#import <Foundation/Foundation.h>\n#import <ApplicationServices/ApplicationServices.h>\nstatic NSUInteger warpCalls;\nstatic CGError TestWarp(CGPoint p){(void)p;warpCalls++;return kCGErrorSuccess;}\n#define CGWarpMouseCursorPosition TestWarp\n#define main BeaverBindingMain\n#include "'+str(SOURCE)+'"\n#undef main\n'+r'''int main(void){@autoreleasepool {
            response=[NSMutableDictionary dictionary];request=@{@"operation":@"click"};BOOL refused=NO;
            @try {SynchronizePointer(NULL,@{@"x":@1,@"y":@1});} @catch(NSException *e){refused=[response[@"errorCode"] isEqual:@"CURSOR_MODE_REQUIRED"];}
            if(!refused||warpCalls||posted||response[@"cursorSyncHistory"])return 1;
            NSMutableDictionary *prior=[NSMutableDictionary dictionaryWithDictionary:@{@"attempted":@YES,@"completed":@YES,@"target":@[@10,@10]}];
            NSMutableArray *history=[NSMutableArray arrayWithObject:prior];response=[NSMutableDictionary dictionaryWithDictionary:@{@"cursorSyncHistory":history,@"cursorSync":prior}];
            activeCursorSyncRecord=prior;pointerSyncComplete=YES;targetPid=INT_MAX;request=@{@"operation":@"drag",@"cursorMode":@"sync-owned-window"};
            BOOL stopped=NO;@try {SynchronizePointer(NULL,@{@"x":@20,@"y":@20});} @catch(NSException *e){stopped=YES;}
            NSDictionary *next=history.lastObject;
            return stopped&&history.count==2&&[prior[@"attempted"] boolValue]&&[prior[@"completed"] boolValue]&&![next[@"attempted"] boolValue]&&![next[@"completed"] boolValue]&&warpCalls==0&&posted==0?0:1;
        }}''')
        subprocess.run(cls.flags+[str(no_mode),'-o',str(cls.no_mode)],check=True,capture_output=True)
        # Execute the actual production gesture branch with all OS/input
        # boundaries stubbed. This checks sequencing without UI or cursor use.
        runtime=SOURCE.read_text();begin=runtime.index('                        BOOL right=',runtime.index('if([op isEqual:@"click"]||[op isEqual:@"drag"])'))
        end=runtime.index('                    } else {',begin);gesture=runtime[begin:end]
        sequence=cls.root/'sequence.m'
        sequence.write_text('#define main BeaverBindingMain\n#include "'+str(SOURCE)+'"\n#undef main\n'+r'''static NSMutableArray *actions;
static NSEventType lastType;
static NSDictionary *lastPoint;
static void NoCheck(AXUIElementRef app){(void)app;}
static CGPoint NoPoint(NSDictionary *point){return CGPointMake([point[@"x"] doubleValue],[point[@"y"] doubleValue]);}
static void NoSync(AXUIElementRef app,NSDictionary *point){(void)app;[actions addObject:@{@"sync":point}];}
static CGEventRef NoCreate(NSEventType type,NSDictionary *point){lastType=type;lastPoint=point;return NULL;}
static void NoPost(AXUIElementRef app,CGEventRef event){(void)app;(void)event;[actions addObject:@{@"event":@(lastType),@"point":lastPoint}];}
#define Recheck NoCheck
#define RelativePoint NoPoint
#define SynchronizePointer NoSync
#define WindowMouseEvent NoCreate
#define Post NoPost
static NSArray *Exercise(BOOL sync,BOOL drag){
    actions=[NSMutableArray array];NSMutableDictionary *spec=[NSMutableDictionary dictionaryWithDictionary:@{@"operation":drag?@"drag":@"click",@"x":@1,@"y":@2,@"points":@[@{@"x":@1,@"y":@2},@{@"x":@3,@"y":@4},@{@"x":@5,@"y":@6}]}];
    if(sync)spec[@"cursorMode"]=@"sync-owned-window";request=spec;NSString *op=request[@"operation"];AXUIElementRef app=NULL;
'''+gesture+r'''
    return actions;
}
int main(void){@autoreleasepool {NSDictionary *result=@{@"click":Exercise(NO,NO),@"syncClick":Exercise(YES,NO),@"drag":Exercise(NO,YES),@"syncDrag":Exercise(YES,YES)};NSData *out=[NSJSONSerialization dataWithJSONObject:result options:0 error:nil];fwrite(out.bytes,1,out.length,stdout);return 0;}}
''')
        subprocess.run(cls.flags+[str(sequence),'-o',str(cls.sequence)],check=True,capture_output=True)




    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def request(self,**changes):
        return dict(operation='windows',pid=2147483647,startTime=[1,0],executableDevice=1,executableInode=1,bundleIdentifier='invalid.no.running.app',**changes)

    def blocked(self,value,code=None,binary=None):
        raw=value if isinstance(value,bytes) else json.dumps(value).encode()
        result=subprocess.run([str(binary or self.binary)],input=raw,capture_output=True,timeout=12)
        self.assertEqual(result.returncode,3,result.stdout)
        output=json.loads(result.stdout);self.assertEqual(output['status'],'blocked');self.assertEqual(output['eventsPosted'],0);self.assertEqual(output['inputDelivery'],'not-posted');self.assertEqual(result.stderr,b'')
        if code:self.assertEqual(output['errorCode'],code)
        return output

    def test_permission_denial_never_prompts_or_posts(self):
        self.blocked(self.request(),'AX_PERMISSION_REQUIRED',self.denied)
        close=self.request();close.update(operation='close',windowId=1)
        result=self.blocked(close,'AX_PERMISSION_REQUIRED',self.denied)
        self.assertEqual(result['axActionsAttempted'],0)

    def test_invalid_json_size_unknown_fields_and_types(self):
        self.blocked(b'{broken','INVALID_JSON')
        self.blocked(b' '*65537,'REQUEST_TOO_LARGE')
        for changes in [{'pid':True},{'pid':1.5},{'startTime':[1,1000000]},{'executableInode':False},{'unexpected':'no'},{'operation':'launch'}]:
            request=self.request();request.update(changes)
            with self.subTest(changes=changes):self.blocked(request,'INVALID_OPERATION' if changes.get('operation')=='launch' else 'INVALID_REQUEST')

    def test_input_requests_reject_before_permissions_or_events(self):
        bad=[dict(operation='click',windowId=1,x=0,y=0,button='middle'),dict(operation='click',x=0,y=0),dict(operation='key',windowId=1,key='arbitrary-key'),dict(operation='key',windowId=1,key='return',flags=1),dict(operation='text',windowId=1,text='x'*257),dict(operation='drag',windowId=1,points=[dict(x=0,y=0)]*65)]
        for changes in bad:
            request=self.request();request.update(changes)
            with self.subTest(operation=changes['operation']):self.blocked(request,'INVALID_REQUEST')

    def test_nonexistent_pid_never_binds_or_launches(self):
        result=self.blocked(self.request())
        self.assertIn(result['errorCode'],['AX_PERMISSION_REQUIRED','PROCESS_NOT_FOUND','PROCESS_IDENTITY_UNAVAILABLE'])

    def test_wrong_birth_of_existing_process_cannot_bind(self):
        request=self.request();request['pid']=os.getpid()
        result=self.blocked(request)
        self.assertIn(result['errorCode'],['AX_PERMISSION_REQUIRED','PROCESS_BIRTH_MISMATCH','PROCESS_IDENTITY_UNAVAILABLE'])

    def test_mouse_window_annotations_roundtrip_without_posting(self):
        result=subprocess.run([str(self.routing)],capture_output=True,timeout=12)
        self.assertEqual(result.returncode,0,result.stderr)
        receipt=json.loads(result.stdout);self.assertTrue(receipt['passed']);self.assertEqual(receipt['cases'],63);self.assertEqual(receipt['eventsPosted'],0);self.assertTrue(receipt['outsideRefused']);self.assertEqual(result.stderr,b'')

    def test_source_forbids_location_setter_global_post_and_private_routing_fields(self):
        source=SOURCE.read_text()
        self.assertNotIn('CGEventSetLocation(',source)
        self.assertNotIn('CGEventPost(',source)
        self.assertNotIn('CGEventPostToPSN(',source)
        self.assertNotRegex(source,r'\bCGS[A-Z]\w*\s*\(')
        self.assertNotRegex(source,r'CGEventSet(?:Integer|Double)ValueField\([^,]+,\s*(?:\([^)]*\)\s*)?\d')
        self.assertIn('CGEventPostToPid(targetPid,event)',source)

    def test_cursor_mode_is_closed_and_only_supported_for_mouse_gestures(self):
        for mode in [None,True,1,'automatic','none','global']:
            request=self.request();request.update(operation='click',windowId=1,x=1,y=1,cursorMode=mode)
            with self.subTest(mode=mode):self.blocked(request,'INVALID_CURSOR_MODE')
        for operation in ['observe','close','text','key']:
            request=self.request();request.update(operation=operation,windowId=1,cursorMode='sync-owned-window')
            with self.subTest(operation=operation):self.blocked(request,'INVALID_REQUEST')

    def test_opted_in_gestures_cannot_sync_when_permission_or_identity_fails(self):
        for operation,fields in [('click',dict(x=1,y=1)),('drag',dict(points=[dict(x=1,y=1),dict(x=2,y=2)]))]:
            request=self.request();request.update(operation=operation,windowId=1,cursorMode='sync-owned-window',**fields)
            denied=self.blocked(request,'AX_PERMISSION_REQUIRED',self.denied)
            self.assertEqual(denied['cursorSyncAttemptedCount'],0);self.assertEqual(denied['cursorSyncCompletedCount'],0)
            self.assertFalse(denied['cursorPositionMayHaveChanged']);self.assertFalse(denied['cursorRestorationAttempted'])
            missing=self.blocked(request)
            self.assertIn(missing['errorCode'],['AX_PERMISSION_REQUIRED','PROCESS_NOT_FOUND','PROCESS_IDENTITY_UNAVAILABLE'])
            self.assertEqual(missing['cursorSyncAttemptedCount'],0);self.assertFalse(missing['cursorPositionMayHaveChanged'])

    def test_internal_sync_requires_opt_in_and_next_point_preserves_partial_history(self):
        result=subprocess.run([str(self.no_mode)],capture_output=True,timeout=12)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,b'');self.assertEqual(result.stderr,b'')

    def test_actual_gesture_branch_adds_one_initial_move_only_for_explicit_sync(self):
        run=subprocess.run([str(self.sequence)],capture_output=True,timeout=12)
        self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stderr,b'')
        cases=json.loads(run.stdout)
        def actions(name):return ['sync' if 'sync' in row else row['event'] for row in cases[name]]
        self.assertEqual(actions('click'),[1,2])
        self.assertEqual(actions('syncClick'),['sync',5,1,2])
        self.assertEqual(actions('drag'),[1,6,6,2])
        self.assertEqual(actions('syncDrag'),['sync',5,1,'sync',6,'sync',6,2])
        sync_drag=cases['syncDrag']
        self.assertEqual(sync_drag[1]['point'],{'x':1,'y':2})
        self.assertEqual(sync_drag[4]['point'],{'x':3,'y':4})
        self.assertEqual(sync_drag[6]['point'],{'x':5,'y':6})
        self.assertEqual(sync_drag[7]['point'],{'x':5,'y':6})
