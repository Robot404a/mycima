import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { computeSeatGeometry, seatColor } from "../lib/seats";

function Seat({ seat, position, selected, onToggle, onHover }) {
  const [hovered, setHovered] = useState(false);
  const color = seatColor(seat, selected);
  const interactive = seat.status === "AVAILABLE" || selected;
  const y = hovered ? 0.11 : 0;

  return (
    <group
      position={[position.x, -0.2 + y, position.z]}
      onClick={(event) => {
        event.stopPropagation();
        onToggle?.(seat);
      }}
      onPointerOver={(event) => {
        event.stopPropagation();
        setHovered(true);
        onHover?.(seat);
        document.body.style.cursor = interactive ? "pointer" : "not-allowed";
      }}
      onPointerOut={() => {
        setHovered(false);
        onHover?.(null);
        document.body.style.cursor = "";
      }}
    >
      <mesh position={[0, 0.06, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.68, 0.16, 0.55]} />
        <meshStandardMaterial
          color={color}
          roughness={0.42}
          metalness={0.18}
          emissive={selected || hovered ? color : "#000000"}
          emissiveIntensity={selected ? 0.55 : hovered ? 0.2 : 0}
        />
      </mesh>
      <mesh position={[0, 0.27, -0.2]} castShadow>
        <boxGeometry args={[0.68, 0.45, 0.12]} />
        <meshStandardMaterial
          color={color}
          roughness={0.46}
          metalness={0.16}
          emissive={selected ? color : "#000000"}
          emissiveIntensity={selected ? 0.4 : 0}
        />
      </mesh>
      {seat.category !== "REGULAR" ? (
        <>
          <mesh position={[0, 0.075, 0.31]}>
            <boxGeometry args={[0.5, 0.035, 0.035]} />
            <meshBasicMaterial
              color={seat.category === "VVIP" ? "#f2d99d" : "#d8c49b"}
              toneMapped={false}
            />
          </mesh>
          <mesh position={[0, 0.14, 0]} scale={[0.5, 0.5, 0.5]}>
            <boxGeometry args={[0.1, 0.1, 0.1]} />
            <meshBasicMaterial
              color={seat.category === "VVIP" ? "#f2d99d" : "#d8c49b"}
              toneMapped={false}
            />
          </mesh>
        </>
      ) : null}
    </group>
  );
}

function Screen({ geometry }) {
  const width = Math.max(5, geometry.floorWidth * 0.72);
  const z = geometry.minZ - 2.15;
  return (
    <group position={[0, 0.2, z]}>
      <mesh position={[0, 0.9, 0]}>
        <planeGeometry args={[width, 1.35]} />
        <meshBasicMaterial color="#f1ead8" toneMapped={false} side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[0, 0.9, 0.01]}>
        <planeGeometry args={[width * 1.03, 1.5]} />
        <meshBasicMaterial color="#c9a45c" transparent opacity={0.18} side={THREE.DoubleSide} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0.45]}>
        <planeGeometry args={[width * 1.2, 1.1]} />
        <meshBasicMaterial color="#c9a45c" transparent opacity={0.06} />
      </mesh>
      <pointLight position={[0, 1.2, 1.2]} intensity={22} distance={9} color="#f3e6c8" />
    </group>
  );
}

function HallScene({ seats, layout, selectedIds, onToggle, onHover }) {
  const geometry = useMemo(() => computeSeatGeometry(seats, layout), [seats, layout]);
  const floorColor = "#0a0b10";

  return (
    <>
      <fog attach="fog" args={["#06070a", 14, 30]} />
      <ambientLight intensity={0.62} />
      <directionalLight position={[0, 9, 5]} intensity={1.8} color="#f5e8d0" castShadow={false} />
      <pointLight position={[-7, 4, 4]} intensity={18} color="#6379c9" />
      <pointLight position={[7, 3.5, 2]} intensity={12} color="#c9784d" />
      <Screen geometry={geometry} />
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -0.36, geometry.maxZ * 0.1]}
        receiveShadow
      >
        <planeGeometry args={[geometry.floorWidth, geometry.floorDepth]} />
        <meshStandardMaterial color={floorColor} metalness={0.55} roughness={0.48} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.35, geometry.maxZ * 0.1]}>
        <ringGeometry args={[geometry.floorWidth * 0.32, geometry.floorWidth * 0.325, 128]} />
        <meshBasicMaterial color="#4a3a22" transparent opacity={0.34} />
      </mesh>
      {seats.map((seat) => {
        const position = geometry.geometry.get(seat.seat_id);
        if (!position) return null;
        return (
          <Seat
            key={seat.seat_id}
            seat={seat}
            position={position}
            selected={selectedIds.has(seat.seat_id)}
            onToggle={onToggle}
            onHover={onHover}
          />
        );
      })}
      <OrbitControls
        makeDefault
        enablePan={false}
        minDistance={7}
        maxDistance={22}
        minPolarAngle={0.35}
        maxPolarAngle={Math.PI / 2.12}
        target={[0, -0.1, 0.2]}
        enableDamping
        dampingFactor={0.07}
      />
    </>
  );
}

export function SeatMap3D({ seats, layout, selectedIds, onToggle, onHover }) {
  const selected = selectedIds instanceof Set ? selectedIds : new Set(selectedIds || []);
  return (
    <div className="hall-canvas-wrap">
      <Canvas
        dpr={[1, 1.7]}
        shadows={false}
        camera={{ position: [0, 9.2, 12.8], fov: 42, near: 0.1, far: 60 }}
        gl={{ antialias: true, powerPreference: "high-performance" }}
      >
        <color attach="background" args={["#07080c"]} />
        <HallScene
          seats={seats}
          layout={layout}
          selectedIds={selected}
          onToggle={onToggle}
          onHover={onHover}
        />
      </Canvas>
      <div className="hall-canvas-hint">
        <span>Drag to orbit</span>
        <span>·</span>
        <span>Scroll to zoom</span>
      </div>
    </div>
  );
}
